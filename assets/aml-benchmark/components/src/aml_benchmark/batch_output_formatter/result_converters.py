# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Class for convert the results to dict."""

import copy
import datetime
from typing import Any, Dict, Optional, Tuple, List

import pandas as pd
import tiktoken
from azureml._common._error_definition.azureml_error import AzureMLError

from aml_benchmark.utils.online_endpoint.online_endpoint_model import OnlineEndpointModel
from aml_benchmark.utils.logging import get_logger
from aml_benchmark.utils.online_endpoint.endpoint_utils import EndpointUtilities
from aml_benchmark.batch_inference_preparer.endpoint_data_preparer import EndpointDataPreparer
from aml_benchmark.utils.exceptions import BenchmarkUserException, BenchmarkSystemException
from aml_benchmark.utils.error_definitions import BenchmarkUserError, BenchmarkSystemError


logger = get_logger(__name__)


class ResultConverters:
    """Convert the batch inference output to different results."""

    PERF_OUTPUT_KEYS = [
        "start_time_iso", "end_time_iso", "time_taken_ms", "output_token_count", "input_token_count"]
    METADATA_KEY_IN_RESULT = 'metadata_key'
    PREDICTION_COL_NAME = 'prediction'
    DEFAULT_ISO_FORMAT = '2000-01-01T00:00:00.000000+00:00'
    DEFAULT_PERF_INPUT_TOKEN = 512
    DEFAULT_GROUND_TRUTH = 'ground_truth'
    DEFAULT_ADDITIONAL_COLUMNS = None

    def __init__(
            self, model_type: str, metadata_key: str, data_id_key: str,
            label_key: str, additional_columns: str, ground_truth_df: Optional[pd.DataFrame],
            fallback_value: str, is_performance_test: bool = False
    ) -> None:
        """Init for the result converter."""
        self._model = OnlineEndpointModel(model=None, model_version=None, model_type=model_type)
        self._metadata_key = metadata_key
        self._label_key = label_key
        if additional_columns:
            elements = additional_columns.split(",")
            self._additional_columns = [s.strip() for s in elements if s.strip()]
        else:
            self._additional_columns = None
        self._data_id_key = data_id_key
        self._lookup_dict = {}
        self._fallback_value = fallback_value
        self._is_performance_test = is_performance_test
        if ground_truth_df is not None:
            logger.info("receive ground truth columns {}".format(ground_truth_df.columns))
            for _, row in ground_truth_df.iterrows():
                self._lookup_dict[row[EndpointDataPreparer.PAYLOAD_HASH]] = \
                    {self.ground_truth_column_name: row[EndpointDataPreparer.PAYLOAD_GROUNDTRUTH]}
                if self._additional_columns:
                    for column in self._additional_columns:
                        try:
                            self._lookup_dict[row[EndpointDataPreparer.PAYLOAD_HASH]][column] = \
                                row[column]
                        except KeyError:
                            raise BenchmarkUserException._with_error(
                                AzureMLError.create(
                                    BenchmarkUserError,
                                    error_details=f"Column {column} doesn't exist. \
                                        Please check your data before submitting again.")
                                )

    def convert_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the input result to predictions."""
        if self.is_result_content_safety_failure(result):
            return self._get_fallback_output()
        if not self.is_result_success(result):
            return self._get_fallback_output()
        return self._get_raw_output(result)

    def convert_result_perf(self, result: Dict[str, Any], use_tiktoken: bool) -> Dict[str, Any]:
        """Convert the result to perf metrics."""
        if not self.is_result_success(result):
            return self._get_fallback_output(is_perf=True)
        response = self._get_response(result)
        if not isinstance(response, dict):
            usage = {}
        else:
            usage = copy.deepcopy(response.get('usage', {}))
        for new_key, old_key in zip(
                ResultConverters.PERF_OUTPUT_KEYS, [
                    "start", "end", "latency", "completion_tokens", "prompt_tokens"]):
            if new_key in usage:
                # For the token scenario, no need to do the conversion.
                usage[new_key] = usage[new_key]
            elif "time_iso" in new_key:
                if old_key not in result:
                    logger.warning(
                        "Cannot find {} in result {}. Using default now.".format(old_key, result))
                    usage[new_key] = ResultConverters.DEFAULT_ISO_FORMAT
                    continue
                # Batch score component output the time in seconds.
                dt = datetime.datetime.utcfromtimestamp(result[old_key])
                usage[new_key] = dt.astimezone().isoformat()
            else:
                # For the token and latency scenarios, no need to do the conversion.
                usage[new_key] = usage[old_key] if old_key in usage else result.get(old_key, -1)
            if old_key in usage:
                del usage[old_key]
        if usage['time_taken_ms'] == -1:
            usage['time_taken_ms'] = (result.get('end', -1) - result.get('start', 0)) * 1000
        if self._model.is_oss_model():
            usage['input_token_count'] = self._get_oss_input_token(usage)
            usage['output_token_count'] = self._get_oss_output_token(result, usage)
        if use_tiktoken:
            usage['input_token_count'], usage['output_token_count'] = self._get_tiktoken_count(result)
        for k in ["output_token_count", "input_token_count"]:
            if usage[k] == -1:
                del usage[k]
        usage['batch_size'] = result.get('batch_size', 1)
        return usage

    def convert_result_ground_truth(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the result to ground truth."""
        ground_truth = ''
        use_ground_truth_input = False
        if self._model.is_oss_model():
            if self._additional_columns:
                use_ground_truth_input = True
            if self._metadata_key:
                ground_truth = self._get_request(result)[self._metadata_key][self._label_key]
            elif self.METADATA_KEY_IN_RESULT in result:
                ground_truth = result[self.METADATA_KEY_IN_RESULT][self._label_key]
            else:
                use_ground_truth_input = True
        elif self._model.is_aoai_model() or self._model.is_claude_model():
            use_ground_truth_input = True
        elif self._model.is_vision_oss_model():
            use_ground_truth_input = False
        if use_ground_truth_input:
            request_payload = self._get_request(result)
            payload_hash = EndpointUtilities.hash_payload_prompt(request_payload, self._model)
            ground_truth = self._lookup_dict.get(payload_hash, {self.ground_truth_column_name: ''})
            return ground_truth
        else:
            results = {self.ground_truth_column_name: ground_truth}
        return results

    def _get_raw_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        prediction = ''
        if self._model.is_oss_model():
            prediction = ResultConverters._get_oss_response_result(result)
        elif self._model.is_aoai_model():
            prediction = ResultConverters._get_aoai_response_result(result)
        elif self._model.is_vision_oss_model():
            prediction = ResultConverters._get_vision_oss_response_results(result)
        elif self._model.is_claude_model():
            prediction = ResultConverters._get_claude_response_result(result)
        return {ResultConverters.PREDICTION_COL_NAME: prediction}

    def _get_fallback_output(self, is_perf: bool = False) -> Dict[str, Any]:
        if is_perf:
            result = {k: -1 for k in ResultConverters.PERF_OUTPUT_KEYS}
            result['start_time_iso'] = ResultConverters.DEFAULT_ISO_FORMAT
            result['end_time_iso'] = datetime.datetime.utcnow().isoformat()
        return {ResultConverters.PREDICTION_COL_NAME: self._fallback_value} if not is_perf else result

    def is_result_success(self, result: Dict[str, Any]) -> bool:
        """Check if the result contains a successful response."""
        if 'status' in result and result['status'].lower() != "success":
            return False
        if self._get_response(result) is None:
            logger.warning('Response is None which indicates the failure of the request.')
            return False
        # handle the scenario the 200 with failure in response.
        try:
            _ = self._get_raw_output(result)
        except Exception as e:
            logger.warning(f'Converting meet errors {e}')
            return False
        return True

    def is_result_content_safety_failure(self, result: Dict[str, Any]) -> bool:
        """Check if result failed due to content safety."""
        try:
            response = result.get("response", {})
            policy_violation = "ResponsibleAIPolicyViolation"
            content_filter = "content_filter"
            # If the response is not a dictionary, return False.
            if not isinstance(response, dict):
                return False
            if response.get("error", {}).get("innererror", {}).get("code") == policy_violation:
                return True
            if response.get("choices", [{}])[0].get("finish_reason") == content_filter:
                return True
        except Exception as e:
            logger.warning(f"Failed to check for content safety responses due to {e}")
        return False

    def _get_oss_input_token(self, perf_metrics: Any) -> Tuple[int, int]:
        if self._is_performance_test:
            return ResultConverters.DEFAULT_PERF_INPUT_TOKEN
        return perf_metrics.get('input_token_count', -1)

    def _get_oss_output_token(self, result: Any, perf_metrics: Any) -> Tuple[int, int]:
        input_parameters = ResultConverters._get_oss_input_parameters(result)
        return input_parameters.get("max_new_tokens", perf_metrics.get('output_token_count', -1))

    def _get_tiktoken_count(self, result: Any) -> Tuple[int, int]:
        input: List[str] = self._get_request_content(result)
        if self._model.is_oss_model():
            output: str = ResultConverters._get_oss_response_result(result)
        elif self._model.is_aoai_model():
            output: str = ResultConverters._get_aoai_response_result(result)
        else:
            raise BenchmarkSystemException._with_error(
                AzureMLError.create(
                    BenchmarkSystemError,
                    error_details=f"Unsupported model type: {self._model.model_type}. Expected `oss` or `aoai`."))

        encoding = tiktoken.get_encoding("cl100k_base")
        input_tokens = sum([len(encoding.encode(input_str)) for input_str in input])
        output_tokens = len(encoding.encode(output))
        return input_tokens, output_tokens

    def _get_additional_columns_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        additional_columns_data = {}
        if self._additional_columns:
            for k in self._additional_columns:
                if k in data.keys():
                    additional_columns_data[k] = data[k]
                else:
                    raise BenchmarkUserException._with_error(
                        AzureMLError.create(
                            BenchmarkUserError,
                            error_details=f"Column {k} doesn't exist. Please check your data before submitting again.")
                        )
        return additional_columns_data

    @property
    def ground_truth_column_name(self) -> str:
        """Get the output ground truth column name."""
        return self._label_key if self._label_key else ResultConverters.DEFAULT_GROUND_TRUTH

    @property
    def additional_columns(self) -> str:
        """Get the additional column names."""
        return self._additional_columns if self._additional_columns else ResultConverters.DEFAULT_ADDITIONAL_COLUMNS

    @staticmethod
    def _get_oss_input_parameters(result: Any) -> Any:
        return ResultConverters._get_request(result)['input_data'].get('parameters', {})

    @staticmethod
    def _get_request(result: Dict[str, Any]) -> Any:
        return result['request']

    @staticmethod
    def _get_response(result: Dict[str, Any]) -> Any:
        return result.get('response', None)

    def _get_request_content(self, result: Dict[str, Any]) -> List[str]:
        if self._model.is_aoai_model():
            request = self._get_request(result)
            if "prompt" in request:
                return [request["prompt"]]
            elif "messages" in request:
                return [my_dict.get('content', '') for my_dict in request['messages']]
            else:
                raise BenchmarkSystemException._with_error(
                    AzureMLError.create(
                        BenchmarkSystemError,
                        error_details=("Cannot find key `prompt` or `messages` "
                                       f"for model type aoai in `request`: {request}.")))
        elif self._model.is_oss_model():
            request = self._get_request(result)['input_data']['input_string']
            if isinstance(request[0], str):
                return [content for content in request]
            elif isinstance(request[0], dict):
                return [my_dict.get('content', '') for my_dict in request]
            else:
                raise BenchmarkSystemException._with_error(
                    AzureMLError.create(
                        BenchmarkSystemError,
                        error_details=("Expected `str` or `dict` for model type oss. "
                                       f"Unknown type of `request`: {request}.")))

    @staticmethod
    def _get_aoai_response_result(result: Dict[str, Any]) -> Any:
        response = ResultConverters._get_response(result)
        response_message = response["choices"][0]
        if "text" in response_message:
            # This is the text generation OAI contract scenario.
            return response_message["text"]
        if "message" in response_message:
            # This is the chat completion OAI contract scenario.
            if "content" in response_message["message"]:
                return response_message["message"]["content"]
            # If content is not there, that means the model filtered the response.
            return ""
        # Unknown contract specified as OAI.
        raise BenchmarkUserException._with_error(
            AzureMLError.create(
                BenchmarkUserError,
                error_details="Endpoint returned response with unknown contract. \
                    Please specify correct model type."
            )
        )

    @staticmethod
    def _get_oss_response_result(result: Dict[str, Any]) -> Any:
        response = ResultConverters._get_response(result)
        if isinstance(response, str):
            return response
        if isinstance(response, list):
            if "0" in response[0]:
                return response[0]["0"]
            return response[0]['output']
        if '0' in response:
            return response['0']
        return response['output']

    @staticmethod
    def _get_claude_response_result(result: Dict[str, Any]) -> Any:
        response = ResultConverters._get_response(result)
        return response["completion"]

    @staticmethod
    def _get_vision_oss_response_results(result: Dict[str, Any]) -> Any:
        response = ResultConverters._get_response(result)
        return response

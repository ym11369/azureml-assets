## Model Description

# FLOR-1.3B

## Table of Contents
<details>
<summary>Click to expand</summary>

- [Model description](#model-description)
- [Intended uses and limitations](#intended-uses-and-limitations)
- [How to use](#how-to-use)
- [Limitations and bias](#limitations-and-bias)
- [Training](#training)
- [Evaluation](#evaluation)
- [Additional information](#additional-information)

</details>

## Model description

**FLOR-1.3B** is a 1.3B-parameter transformer-based causal language model for Catalan, Spanish, and English. 
It is the result of a language adaptation technique performed on [BLOOM-1.7B](https://huggingface.co/bigscience/bloom-1b7), 
which involves modifying the model's vocabulary and embedding layer, and continuously pre-training the model with 26B tokens in our target languages.

For more details, take a look at [this blogpost](https://medium.com/@mpamies247/flor-6-3b-a-chinchilla-compliant-model-for-catalan-spanish-and-english-7cdb389a9aac) about the project.

## Intended uses and limitations

The **FLOR-1.3B** model is ready-to-use only for causal language modeling. 
It can perform text-generation tasks and be fine-tuned for specific scenarios.

## How to use
```python
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

input_text = "Sovint em trobo pensant en tot allò que"

model_id  = "projecte-aina/FLOR-1.3B"
tokenizer = AutoTokenizer.from_pretrained(model_id)
generator = pipeline(
    "text-generation",
    model=model_id,
    tokenizer=tokenizer,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
    device_map="auto",
)
generation = generator(
    input_text,
    do_sample=True,
    top_k=10,
    eos_token_id=tokenizer.eos_token_id,
)

print(f"Result: {generation[0]['generated_text']}")
```

## Limitations and bias
At the time of submission, no measures have been taken to estimate the bias and toxicity embedded in the model. 
However, we are well aware that our models may be biased since the corpora have been collected using crawling techniques 
on multiple web sources. We intend to conduct research in these areas in the future, and if completed, this model card will be updated. 


## Training

### Language adaptation and training

The language adaptation technique used to create FLOR-1.3B requires the vocabulary of the source model 
to be adapted before continuing its pre-training with data in the target languages. Specifically, we proceeded as follows:
1) We trained our own BPE tokenizer for Catalan, Spanish, and English, and replaced the original BLOOM tokenizer and vocabulary with it. This procedure implied a downsizing of the original BLOOM's embedding layer and, therefore, a model compression from 1.7B parameters to 1.3B.
2) The embeddings corresponding to tokens that are present in both the original and the target vocabulary (matching tokens) were used for initialization.
3) The embeddings from tokens not present in BLOOM's original vocabulary were initialized as the average of all embeddings.
4) The model was initialized with the weights from BOOM-1.7B, and with our adapted tokenizer (step 1) and embeddings (steps 2-3).
5) The model was then trained on a corpus that contains a mixture of Catalan, Spanish, and English data.

### Training data

The training corpus is the same that was used to train [Ǎguila-7B](https://huggingface.co/projecte-aina/aguila-7b).
It consists of 26B tokens of several corpora gathered from web crawlings and public domain data.

| Dataset             | Language | Words (per-epoch) | Epochs       |
|---------------------|----------|--------------------|--------------|
| Wikipedia           | en       |           2169.97M |  1.428144485 |
| C4_es               | es       |          53709.80M | 0.1049686196 |
| Biomedical          | es       |            455.03M | 0.7140722425 |
| Legal               | es       |            995.70M | 0.7140722425 |
| Wikipedia           | es       |            693.60M |  1.428144485 |
| Gutenberg           | es       |             53.18M | 0.7140722425 |
| C4_ca               | ca       |           2826.00M |  2.142216727 |
| Biomedical          | ca       |             11.80M |  1.428144485 |
| RacoCatalà Noticias | ca       |             17.16M |  2.142216727 |
| RacoCatalà Forums   | ca       |            333.73M |  2.142216727 |
| CaWaC               | ca       |             57.79M |  2.142216727 |
| Wikipedia           | ca       |            228.01M |  3.570361212 |
| Vilaweb             | ca       |             50.34M |  2.142216727 |

### Languages

The training data has the same amount of Catalan and Spanish texts, and a smaller amount of English data. 
The table below shows the final language distribution:

|Language|Percentage|
|--------|----------|
|   English (EN)   |  16.84%  |
|   Spanish (ES)   |  41.38%  |
|   Catalan (CA)   |  41.79%  |

### Training hyperparameters

- seed: 1
- distributed_type: [WSE-2](https://www.cerebras.net/product-chip/)
- num_devices: 1
- train_batch_size: 60
- eval_batch_size:  60
- optimizer: AdamW
- betas: (0.9,0.95)
- epsilon: 1e-08
- weight_decay_rate: 0.1
- learning_rate:
  - scheduler: "Linear" \
    initial_learning_rate: 0.0 \
    end_learning_rate: 4.1e-5 \
    steps: 3050
  - scheduler: "CosineDecay" \
    initial_learning_rate: 4.1e-5 \
    end_learning_rate: 3.4e-6 \
    steps: 209133
  - scheduler: "Constant" \
    learning_rate: 2.2e-6
- num_epochs: 1.0

### Framework
The training was conducted in a Cerebras' [CS-2 system](https://www.cerebras.net/product-system/) 
using the [cs-1.9.1](https://github.com/Cerebras/modelzoo/releases/tag/Release_1.9.1) release of their software.

## Evaluation
FLOR-1.3B has been evaluated in a 5-shot setting, using EleutherAI's *LM Evaluation Harness*. 
The evaluation benchmark includes tasks in Catalan, Spanish, and English, with particular emphasis on Catalan datasets.

The tasks were chosen to cover several evaluation areas in order to provide a comprehensive overview of the model's capabilities. 
The baselines used to compare our results are multilingual and English open-source 1.3B models: 
mGPT-1.3B, GPT-Neo-1.3B, Pythia-1.4B, OPT-1.3B, Falcon-rw-1.3B, and Cerebras-GPT-1.3B.

Our implementation of EleutherAI's *LM Evaluation Harness* can be found [here](https://github.com/langtech-bsc/lm-evaluation-harness?files=1).

The following is a list of evaluation areas and their respective datasets:
- Reading Comprehension: [Belebele](https://huggingface.co/datasets/facebook/belebele)
- Question Answering: [XQuAD](https://huggingface.co/datasets/xquad), [CatalanQA](https://huggingface.co/datasets/projecte-aina/catalanqa), [CoQCat](https://huggingface.co/datasets/projecte-aina/CoQCat)
- Natural Language Inference: [XNLI](https://huggingface.co/datasets/xnli) and its translation to Catalan ([XNLI-ca](https://huggingface.co/datasets/projecte-aina/xnli-ca)), [TE-ca](https://huggingface.co/datasets/projecte-aina/teca)
- Paraphrase Identification: [PAWS-X](https://huggingface.co/datasets/paws-x) and its translation to Catalan ([PAWS-ca](https://huggingface.co/datasets/projecte-aina/PAWS-ca)), [Parafraseja](https://huggingface.co/datasets/projecte-aina/Parafraseja)
- Commonsense Reasoning: [COPA](https://people.ict.usc.edu/~gordon/copa.html) and its translation to Catalan ([COPA-ca](https://huggingface.co/datasets/projecte-aina/COPA-ca))
- Translation: [FLoRes](https://huggingface.co/datasets/flores)

### Reading Comprehension and Questions Answering

| Model | Belebele-ca | Belebele-es | Belebele-en | XQuAD-ca | XQuAD-es | XQuAD-en | CatalanQA | CoQCat |
| ------|:-----------:|:-----------:|:-----------:|:--------:|:--------:|:--------:|:---------:|:------:|
Random | 25.00 | 25.00 | 25.00 | - | - | - | - | - |
mGPT-1.3B | 26.64 | 25.82 | 28.07 | 0.33 | 0.67 | 0.17 | 0.65 | 0.78 |
GPT-Neo-1.3B | 39.55 | 37.50 | 42.83 | 19.75 | 29.77 | 51.53 | 22.34 | 23.57 |
Pythia-1.4B | 38.32 | 36.89 | 44.26 | 26.19 | 34.13 | 52.98 | 27.47 | 25.38 |
OPT-1.3B | 35.86 | 37.09 | 45.49 | 23.53 | 31.85 | 52.95 | 26.58 | 20.18 |
Falcon-rw-1.3B | 34.84 | 35.66 | **50.61** | 5.93 | 19.25 | **58.60** | 6.91 | 15.61 |
Cerebras-GPT-1.3B | 32.79 | 31.76 | 35.04 | 8.56 | 19.98 | 36.00 | 10.87 | 14.12 |
BLOOM-1.1B | 39.34 | **38.32** | 41.19 | 36.81 | 36.98 | 44.10 | 44.65 | 34.57 |
FLOR-1.3B | **43.85** | 38.11 | 40.57 | **43.52** | **44.31** | 44.11 | **54.25** | **48.15** |


### Natural Language Inference and Paraphrase Identification

| Model | XNLI-ca | XNLI-es | XNLI-en | TECA-ca | PAWS-X-ca | PAWS-X-es | PAWS-X-en | Parafraseja |
| ------|:-------:|:-------:|:-------:|:-------:|:---------:|:---------:|:---------:|:-----------:|
Random | 33.33 | 33.33 | 33.33 | 33.33 | 50.00 | 50.00 | 50.00 | 50.00 |
mGPT-1.3B | 40.06 | 43.81 | 45.67 | 37.03 | 51.00 | 52.30 | 56.15 | 51.32 |
GPT-Neo-1.3B | 41.44 | 45.57 | 49.92 | 35.38 | 54.65 | 53.40 | 54.60 | 51.70 |
Pythia-1.4B | 42.46 | 45.61 | 51.00 | 37.46 | 54.15 | 52.50 | **57.70** | 55.23 |
OPT-1.3B | 40.08 | 44.53 | **52.48** | 36.14 | 54.10 | 52.55 | 55.90 | 53.23 |
Falcon-rw-1.3B | 34.53 | 35.85 | 45.73 | 34.96 | 54.25 | **54.05** | 53.65 | 50.60 |
Cerebras-GPT-1.3B | 36.83 | 38.88 | 47.25 | 35.62 | 52.40 | 52.20 | 55.95 | 52.05 |
BLOOM-1.1B | 47.19 | 46.39 | 49.44 | 41.38 | **55.05** | 54.05 | 54.75 | 55.65 |
FLOR-1.3B | **49.20** | **48.82** | 47.45 | **42.89** | 53.20 | 52.85 | 53.00 | **57.43** |


### Commonsense Reasoning and Translation

| Model | XStoryCloze-es | XStoryCloze-en | COPA-ca | COPA-en | FloRes (ca->es) | FloRes (es->ca) | FloRes (ca->en) | FloRes (en->ca) | FloRes (es->en) | FloRes (en->es) | 
| ------|:--------------:|:--------------:|:-------:|:-------:|:---------------:|:---------------:|:---------------:|:---------------:|:---------------:|:---------------:|
Random | 50.00 | 50.00 | 50.00 | 50.00 | - | - | - | - | - | - |
mGPT-1.3B | 55.33 | 60.09 | 52.20 | 63.40 | 3.25 | 2.96 | 9.25 | 3.79 | 17.75 | 15.34 |
GPT-Neo-1.3B | 51.42 | 66.58 | 53.40 | 74.80 | 3.27 | 3.80 | 17.77 | 5.49 | 17.70 | 12.04 |
Pythia-1.4B | 54.14 | 68.37 | 52.20 | 78.60 | 9.68 | 5.74 | 24.03 | 11.10 | 21.50 | 15.04 |
OPT-1.3B | 53.94 | 69.95 | 52.60 | 76.20 | 3.14 | 3.52 | 15.39 | 2.00 | 16.33 | 6.53 |
Falcon-rw-1.3B | 51.09 | **71.34** | 52.40 | **79.60** | 3.03 | 3.59 | 8.89 | 3.01 | 14.17 | 6.50 |
Cerebras-GPT-1.3B | 49.11 | 60.62 | 51.40 | 66.80 | 2.42 | 1.81 | 2.69 | 0.82 | 3.36 | 1.77 |
BLOOM-1.1B | 57.91 | 62.48 | 62.80 | 66.40 | 21.62 | 15.28 | 31.16 | 21.28 | 20.92 | 16.84 |
FLOR-1.3B | **64.06** | 61.81 | **68.00** | 67.80 | **22.16** | **18.58** | **33.95** | **29.31** | **23.09** | **20.30** |

## Additional information

### Author
The Language Technologies Unit from Barcelona Supercomputing Center.

### Contact
For further information, please send an email to <langtech@bsc.es>.

### Copyright
Copyright(c) 2023 by Language Technologies Unit, Barcelona Supercomputing Center.

### License
[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)

### Funding
This work was funded by [Departament de la Vicepresidència i de Polítiques Digitals i Territori de la Generalitat de Catalunya](https://politiquesdigitals.gencat.cat/ca/inici/index.html#googtrans(ca|en) within the framework of [Projecte AINA](https://politiquesdigitals.gencat.cat/ca/economia/catalonia-ai/aina).

### Disclaimer

<details>
<summary>Click to expand</summary>

The model published in this repository is intended for a generalist purpose and is available to third parties under a permissive Apache License, Version 2.0. 

Be aware that the model may have biases and/or any other undesirable distortions.

When third parties deploy or provide systems and/or services to other parties using this model (or any system based on it) 
or become users of the model, they should note that it is their responsibility to mitigate the risks arising from its use and, 
in any event, to comply with applicable regulations, including regulations regarding the use of Artificial Intelligence.

In no event shall the owner and creator of the model (Barcelona Supercomputing Center) 
be liable for any results arising from the use made by third parties.

</details>

### Inference samples

Inference type|Python sample (Notebook)|CLI with YAML
|--|--|--|
Real time|[text-generation-online-endpoint.ipynb](https://aka.ms/azureml-infer-online-sdk-text-generation)|[text-generation-online-endpoint.sh](https://aka.ms/azureml-infer-online-cli-text-generation)
Batch |[	text-generation-batch-endpoint.ipynb](https://aka.ms/azureml-infer-batch-sdk-text-generation)|coming soon

### Sample inputs and outputs

#### Sample input
```json
{
  "input_data": {
    "input_string": [
      "Once upon a time,"
    ],
    "parameters": {
      "top_p": 0.8,
      "temperature": 0.8,
      "max_new_tokens": 90,
      "do_sample": true
    }
  }
}
```

#### Sample output
```json
[
  {
    "0": "Once upon a time, there were two brothers who lived in the small village of Summerfield. They were known as the brothers Hare and Bunny. They were very good friends and they loved each other dearly.\n\nOne day, the brothers Hare and Bunny went to the fields and they got some apples from the apple tree. When they got the apples, they went to the pond and they drank"
  }
]
```

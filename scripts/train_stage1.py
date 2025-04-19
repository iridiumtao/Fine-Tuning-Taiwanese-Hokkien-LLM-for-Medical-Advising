from datasets import load_dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
from torch import float16

# Load model with LoRA
import torch
torch.cuda.empty_cache() # free the GPU memory, model's too big lol 


# Tokenize: load it first so I can call it in format_prompt to use tokenizer
# model_id = "taide/TAIDE-LX-7B"
model_id = "taide/Llama-3.1-TAIDE-LX-8B-Chat"
tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast = False)
tokenizer.pad_token = tokenizer.eos_token
print("Using fast tokenizer?", tokenizer.is_fast)


# Load dataset
# dataset = load_dataset("json", data_files="../data/medical_qa_with_answer_text.jsonl")
dataset = load_dataset("json", data_files = {"train": "../data/medical_qa_with_answer_text.jsonl"})

print(dataset["train"][0])

# # Format prompt
# def format_prompt(example):
#     prompt = f"### 問題:\n{example['instruction']}\n\n### 回答:\n{example['output']}"
#     return {
#         "prompt": prompt
#     }

# Format prompt (creates "text" key!)
def format_prompt(example, tokenizer):
    return {
        "text": f"<|user|>\n{example['instruction']}\n<|assistant|>\n{example['output']}{tokenizer.eos_token}"
    }

# dataset = dataset.map(format_prompt)
dataset["train"] = dataset["train"].map(lambda ex: format_prompt(ex, tokenizer))


def tokenize(example):
    return tokenizer(example["text"], truncation = True, padding = "max_length", max_length = 512)

#tokenized_dataset = dataset.map(tokenize, batched = True)
tokenized_dataset = dataset["train"].map(tokenize, batched = True)


model = AutoModelForCausalLM.from_pretrained(model_id, device_map={"": 0}, torch_dtype = float16, load_in_8bit = True)

lora_config = LoraConfig(
    r = 8,
    lora_alpha = 16,
    lora_dropout = 0.05,
    task_type = TaskType.CAUSAL_LM
)

model = get_peft_model(model, lora_config)

# Training settings
training_args = TrainingArguments(
    output_dir = "../models/stage1",
    per_device_train_batch_size = 1,
    gradient_accumulation_steps = 8,
    num_train_epochs = 5,
    logging_steps = 10,
    save_strategy = "epoch",
    fp16 = True,
    report_to = "none"
)

# Trainer
data_collator = DataCollatorForLanguageModeling(tokenizer = tokenizer, mlm = False)

trainer = Trainer(
    model = model,
    args = training_args,
    train_dataset = tokenized_dataset,
    tokenizer = tokenizer,
    data_collator = data_collator
)

trainer.train()

# Save model 
model.save_pretrained("../models/stage1")
tokenizer.save_pretrained("../models/stage1")
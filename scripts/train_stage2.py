from datasets import load_dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer, DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
import torch

# === Load dataset from your combined file ===
dataset = load_dataset("json", data_files={"train": "../data/hokkien_pretrain_combined.json"})

# === Tokenizer & Model ===
model_id = "lbh0830/TW-Hokkien-LLM"
tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast = False)
tokenizer.pad_token = tokenizer.eos_token  # required for padding

def tokenize(example):
    return tokenizer(example["text"], truncation=True, padding="max_length", max_length=512)

tokenized_dataset = dataset.map(tokenize, batched=True)

# === Load model with LoRA ===
torch.cuda.empty_cache()

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map={"": 0},
    torch_dtype=torch.float16,
    load_in_8bit=True
)

lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    task_type=TaskType.CAUSAL_LM
)

model = get_peft_model(model, lora_config)

# === Training ===
training_args = TrainingArguments(
    output_dir="../models/stage2",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    num_train_epochs=3,
    logging_steps=10,
    save_strategy="epoch",
    fp16=True,
    report_to="none"
)

data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer,
    data_collator=data_collator
)

trainer.train()

# === Save model ===
model.save_pretrained("../models/stage2")
tokenizer.save_pretrained("../models/stage2")
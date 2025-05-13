from datasets import load_dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer, DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
import torch
import mlflow
import mlflow.pytorch
from accelerate import Accelerator
from transformers import LlamaTokenizer

mlflow.set_tracking_uri("http://127.0.0.1:5000")
mlflow.set_experiment("taigi-llm-training")

# === Load dataset from your combined file ===
dataset = load_dataset("json", data_files={"train": "../data/hokkien_pretrain_combined.jsonl"})

# === Tokenizer & Model ===
# model_id = "../models/stage1"  # load the checkpoint from Stage 1
# tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast = False)
# tokenizer.pad_token = tokenizer.eos_token  # required for padding

model_id = "../models/stage1"
tokenizer = LlamaTokenizer.from_pretrained(model_id, use_fast=False)
tokenizer.pad_token = tokenizer.eos_token

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
    num_train_epochs = 3,
    logging_steps = 10,
    save_strategy = "epoch",
    fp16 = True,
    report_to = "none"
)

data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer,
    data_collator=data_collator
)

with mlflow.start_run():
    # Log config
    mlflow.log_params({
        "lr": training_args.learning_rate,
        "epochs": training_args.num_train_epochs,
        "batch_size": training_args.per_device_train_batch_size
    })

    # Train
    trainer.train()

    # Unwrap the PEFT Accelerate-wrapped model
    unwrapped_model = Accelerator().unwrap_model(model)

    # Log model
    mlflow.pytorch.log_model(unwrapped_model, "model") 

    # Log final metrics (add more if needed)
    mlflow.log_metric("final_train_loss", trainer.state.log_history[-1]['loss'])

trainer.train()

# === Save model ===
unwrapped_model.save_pretrained("../models/stage2",  safe_serialization = True)
tokenizer.save_pretrained("../models/stage2")

mlflow.log_artifacts("./models/stage2", artifact_path="model")
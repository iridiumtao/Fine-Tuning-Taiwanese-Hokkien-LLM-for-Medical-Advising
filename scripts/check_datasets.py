from datasets import load_dataset, concatenate_datasets, get_dataset_config_names

# Load ICorpus-100
icorpus = load_dataset("BohanLu/ICorpus-100")
# Load TAIDE-14-tasks-Hokkien
taide = load_dataset("BohanLu/TAIDE-14-tasks-Hokkien")

from datasets import get_dataset_config_names

all_configs = get_dataset_config_names("BohanLu/TAIDE-14-tasks-Hokkien")
print("Available TAIDE-14 configs:")
for config in all_configs:
    print("-", config)

# Print what splits exist
print("ICorpus-100 splits:", icorpus.keys())
print("TAIDE-14-tasks-Hokkien splits:", taide.keys())

# Now try to print a sample
print("\n--- ICorpus-100 sample ---")
print(icorpus["test"][0])

print("\n--- TAIDE-14-tasks-Hokkien sample ---")
print(taide["train"][0])

def format_icorpus(example):
    return {
        "text": f"<|user|>\n{example['HAN']}\n<|assistant|>\n{example['HAN']}<|endoftext|>"
    }

def format_taide(example):
    return {
        "text": f"<|user|>\n{example['Prompt']}\n<|assistant|>\n<|endoftext|>"
    }


# Map format
formatted_icorpus = icorpus["test"].map(format_icorpus)
formatted_taide = taide["train"].map(format_taide)

# Combine
combined_dataset = concatenate_datasets([formatted_icorpus, formatted_taide])

# Shuffle the combined dataset
combined_dataset = combined_dataset.shuffle(seed = 42)

print("\n--- Combined dataset sample ---")
print(combined_dataset[0])

# Save the combined dataset for stage 2
combined_dataset.to_json("../data/hokkien_pretrain_combined.jsonl", orient = "records", lines = True, force_ascii = False)
print("Combined dataset saved to ../data/hokkien_pretrain_combined.jsonl")
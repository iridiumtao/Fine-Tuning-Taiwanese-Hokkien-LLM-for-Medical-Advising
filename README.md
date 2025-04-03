# MLOps_Project
NYU_MLOps_Spring2025_Project

## Title of project

<!-- 
Discuss: Value proposition: Your will propose a machine learning system that can be 
used in an existing business or service. (You should not propose a system in which 
a new business or service would be developed around the machine learning system.) 
Describe the value proposition for the machine learning system. What’s the (non-ML) 
status quo used in the business or service? What business metric are you going to be 
judged on? (Note that the “service” does not have to be for general users; you can 
propose a system for a science problem, for example.)
-->

### Contributors

<!-- Table of contributors and their roles. 
First row: define responsibilities that are shared by the team. 
Then, each row after that is: name of contributor, their role, and in the third column, 
you will link to their contributions. If your project involves multiple repos, you will 
link to their contributions in all repos here. -->

| Name                            | Responsible for                             | Link to their commits in this repo |
|---------------------------------|---------------------------------------------|------------------------------------|
| All team members                |                                             |                                    |
| Team member 1                   | Model training (unit 4 and 5)               | Ping-Jung(Lawrence)Lu              |
| Team member 2                   | Model serving (unit 6), monitoring (unit 7) | Chun-Ju Tao                        |
| Team member 3                   | Data pipeline (unit 8)                      | TsuYun Chen                        |
| Team member 4 (if there is one) | Continuous X pipeline (unit 3)              | Yi Syuan Chung                     |



### System diagram

<!-- Overall digram of system. Doesn't need polish, does need to show all the pieces. 
Must include: all the hardware, all the containers/software platforms, all the models, 
all the data. -->

#### Taiwanese Medical LLM Construction Process
```mermaid
graph TD
    A[Taiwanese Mandarin LLaMA-2 Base Model] --> B[Fine-tune with Medical Taiwanese Mandarin Corpus]
    B --> C[Medical Taiwanese Mandarin LLM]
    C --> D[Fine-tune with Taiwanese Corpus]
    D --> E[Taiwanese Medical LLM]
    
    %% Data Preparation Blocks
    F[Medical Taiwanese Mandarin Corpus] --Preprocessing--> B
    G[Taiwanese Corpus] --Preprocessing--> D
    H[Partial Medical Taiwanese Mandarin Corpus] --Prevent Forgetting--> D
    
    %% Technical Details
    I[PEFT Techniques\nLoRA/Adapters] --> D
    J[Evaluation Metrics] --> E
    
    %% Styles
    classDef model fill:#f9d4d4,stroke:#333,stroke-width:2px
    classDef data fill:#d4f9d4,stroke:#333,stroke-width:1px
    classDef tech fill:#d4d4f9,stroke:#333,stroke-width:1px
    
    class A,C,E model
    class F,G,H data
    class I,J tech
```
#### Training Stage Details
Stage 1: Medical Taiwanese Mandarin LLM Construction
```mermaid
flowchart LR
    A[Taiwanese Mandarin LLaMA-2] --> B{Fine-tune with Medical Corpus}
    B --> C[Medical Taiwanese Mandarin LLM]
    D[(Medical Taiwanese Mandarin Corpus)] --> E[Data Preprocessing]
    E --> F[Cleaning\nStandardization\nQuality Filtering]
    F --> B
```
Stage 2: Taiwanese Medical LLM Conversion
```mermaid
flowchart LR
    A[Medical Taiwanese Mandarin LLM] --> B{Fine-tune with Taiwanese Corpus}
    B --> C[Taiwanese Medical LLM]
    
    D[(Taiwanese Corpus)] --> E[Taiwanese Data Preprocessing]
    F[(Partial Medical Taiwanese Mandarin Corpus)] --> G[Mixed Dataset]
    E --> G
    G --> B
    
    H[PEFT Techniques] --> B
    I[Curriculum Learning] --> B
```

#### Evaluation and Deployment Process

```mermaid
flowchart TD
    A[Taiwanese Medical LLM] --> B[Evaluation Process]
    B --> C{Meets Standards?}
    C -->|Yes| D[Deploy Model]
    C -->|No| E[Adjust and Retrain]
    E --> A
    
    F[Taiwanese Medical Evaluation Set] --> B
    G[Taiwanese Mandarin Medical Evaluation Set] --> B
    H[General Taiwanese Evaluation Set] --> B
```

### Summary of outside materials

<!-- In a table, a row for each dataset, foundation model. 
Name of data/model, conditions under which it was created (ideally with links/references), 
conditions under which it may be used. -->

|                             | Type       | How it was created                                                                       | Conditions of use                                                                                        |
|-----------------------------|------------|------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| MedQA                       | Dataset    | Collecting QAs and textbooks from multiple regions and processing them into JSONL format | MIT                                                                                                      |
| Taiwanese Corpus (Huē-ji̍p) | Dataset    | Compiling Taiwanese Corpus from Dictionary, News, and more                               | MIT, CC BY-ND 3.0 TW                                                                                     |
| TIADE-LX                    | Base model | Fine-tuning LLaMA2-7B with Taiwanese domain-specific data                                | Free under a non-exclusive, non-transferable license, provided compliance with Meta AI’s Llama 2 license |
| Taiwanese Hokkien LLM       | Base model | Fine-tuning TIADE-LX on a limited Taiwanese corpus                                       | MIT                                                                                                      |


### Summary of infrastructure requirements

<!-- Itemize all your anticipated requirements: What (`m1.medium` VM, `gpu_mi100`), 
how much/when, justification. Include compute, floating IPs, persistent storage. 
The table below shows an example, it is not a recommendation. -->

| Requirement     | How many/when                                     | Justification |
|-----------------|---------------------------------------------------|---------------|
| `m1.medium` VMs | 3 for entire project duration                     | ...           |
| `gpu_mi100`     | 4 hour block twice a week                         |               |
| Floating IPs    | 1 for entire project duration, 1 for sporadic use |               |
| etc             |                                                   |               |

### Detailed design plan

<!-- In each section, you should describe (1) your strategy, (2) the relevant parts of the 
diagram, (3) justification for your strategy, (4) relate back to lecture material, 
(5) include specific numbers. -->

#### Model training and training platforms

<!-- Make sure to clarify how you will satisfy the Unit 4 and Unit 5 requirements, 
and which optional "difficulty" points you are attempting. -->

#### Model serving and monitoring platforms

<!-- Make sure to clarify how you will satisfy the Unit 6 and Unit 7 requirements, 
and which optional "difficulty" points you are attempting. -->

#### Data pipeline

<!-- Make sure to clarify how you will satisfy the Unit 8 requirements,  and which 
optional "difficulty" points you are attempting. -->
    Persistent Storage  
    - **Chameleon Cloud**  

    Offline Data  
    - **JSON**  

    Data Pipelines  

    - Data Sources  
    *(Refer to the outside meterials section above)*  

    1. Med QA (JSON file)  
        - Extract into a **Pandas DataFrame** for preprocessing (formatting, labeling).  
        - Convert into a **Hugging Face dataset** for model training.  

    2. Taiwanese Corpus  
    - Already formatted as a **Hugging Face dataset**, directly used for training.  

    Online Data  
    - **Input text (real-time query)** → Format (combine with previous dialogue if applicable) → Feed into the **LLM for inference**.  

    Additional Steps:  
    - Preprocess input (tokenization, standardization).  
    - Handle streaming queries via **WebSocket/API**.  
    - Log and store responses for further analysis.  

#### Continuous X

##### Infrastructure Setup
- Entire infrastructure in Git, using Terraform (declarative) to provision computing resources.
- Use automation tools Argo Workflows to set up the environment.
- Containerize all components and deploy using a microservices architecture.
##### Data Preprocessing, CI/CD and continuous training 
- Automatically fetch and preprocess new data (Taiwanese medical corpus and general Taiwanese corpus) with a pipeline.
- Fine-tune Taiwanese Mandarin LLaMA-2 with the Medical Corpus to form Medical Taiwanese Mandarin LLM. Further fine-tune this model using Taiwanese Corpus.
- Automated evaluation pipeline runs, if the model does not meet performance standards, the pipeline triggers adjustments and retraining.
##### Deployment Process (Staged Deployment & Cloud-Native)
- Staged deployment process: Staging, Canary Release, Production Rollout.

## Instructions


#### Please do not run any file on your local machine if you don't have enough RAM or GPU, your computer will explode!



### Step1: create Virtual environment: (taigi-env) or any name you prefer

```python
python3 -m venv taigi-env
source taigi-env/bin/activate
```

### Step2: swtich branch: (will merge the branch later)

```python
git checkout master
```

### Step3: Install requirement packages in your virtual environment:

```python
pip install -r requirements.txt
```

__There are some packages that needs to install manually(follow the instructions below):__
```python
pip install sentencepiece --prefer-binary
```

```python
pip install datasets
```


### Step4: Log in hugging face CLI with your own token:

```python
huggingface-cli login
```

### Step5: if you are retrainning the model, if you are not retrainning the model, skip to Step6.

```python
cd scripts/
python3 train_stage1.py
```

__After running train_stage1.py, if it shows an error like this:__
![image](https://github.com/user-attachments/assets/9aa6f123-5f61-4894-bffd-b67a85c4bf6a)


__follow instructions bellow:__

__Step1:__ clear it first:

```python
pip uninstall bitsandbytes -y
```

__Step2:__ reinstall:

```python
pip install bitsandbytes --no-cache-dir
```

__Step3:__ test it with python -m bitsandbytes command, it sould show:

![image](https://github.com/user-attachments/assets/36b4d98d-608b-40f6-910f-3b6cea2aab53)



Than rerun python3 train_stage1.py, it should now work successfully.

### Step6: Run inference.py to Chat with the model:

```python
python3 inference.py
```
You can now enter the question you want to ask.

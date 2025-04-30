# Dockerfile
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

RUN pip install sentencepiece --prefer-binary \
    && pip install datasets
    
    #&& pip install bitsandbytes --force-reinstall --no-cache-dir

COPY models/ ./models/

COPY app.py ./app.py


EXPOSE 8000

# Activate Uvicorn, single worker for now
CMD ["sh", "-c", "\
    mkdir -p ~/.cache/huggingface && \
    echo \"$HUGGINGFACE_TOKEN\" > ~/.cache/huggingface/token && \
    uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1\
"]
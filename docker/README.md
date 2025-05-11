# Docker Compose Deployment

This repository contains Docker Compose configurations for deploying different services:

1. **Backend (Production)** - FastAPI and Gradio services.
2. **Feedback Loop** - Airflow and Label Studio.
3. **Monitoring** - Prometheus and Grafana (separate Compose file).

---

## 🚀 **Quick Start Guide**

### 🔗 **Prepare Docker Network**

Before starting any services, make sure to create the Docker network:

```bash
docker network create production_net
```

This step is required because the `docker-compose` files reference an external network called `production_net`.

---

### Backend Services (FastAPI, Gradio)

```bash
# Start the backend services
docker compose -f ./docker/backend/docker-compose-production.yml up --build -d

# if CPU
docker compose -f ./docker/backend/docker-compose-production-cpu.yml up --build -d

# Stop the backend services
docker compose -f ./docker/backend/docker-compose-production.yml down
```

**Endpoints:**

* FastAPI Server → [http://localhost:8000](http://localhost:8000)
* Gradio Frontend → [http://localhost:7860](http://localhost:7860)

---

### Feedback Loop (Airflow, Label Studio)

```bash
# Start the feedback loop services
docker compose -f ./docker/feedback_loop/docker-compose-airflow.yml up --build -d
docker compose -f ./docker/feedback_loop/docker-compose-labelstudio.yml up --build -d

# Stop the feedback loop services
docker compose -f ./docker/feedback_loop/docker-compose-airflow.yml down
docker compose -f ./docker/feedback_loop/docker-compose-labelstudio.yml down
```

**Endpoints:**

* Airflow → [http://localhost:8081](http://localhost:8081)
* Label Studio → [http://localhost:8080](http://localhost:8080)
  * Label Studio Jupyter Notebook Port: 8888

---

### Monitoring (Prometheus, Grafana)

```bash
# Start the monitoring services
docker compose -f ./docker/monitoring/docker-compose-monitor.yml up --build -d

# Stop the monitoring services
docker compose -f ./docker/monitoring/docker-compose-monitor.yml down
```

**Endpoints:**

* Prometheus → [http://localhost:9090](http://localhost:9090)
* Grafana → [http://localhost:3000](http://localhost:3000)

---

## 🔄 **Rebuild Services**

To rebuild a specific service:

```bash
# Example for backend
docker compose -f ./docker/backend/docker-compose-production.yml up --build -d fastapi_server

# Example for feedback loop
docker compose -f ./docker/feedback_loop/docker-compose-feedback.yml up --build -d airflow
```

---

## 🔑 **Default Login Credentials**

| Service      | Username                | Password        |
|--------------|-------------------------|-----------------|
| Label Studio | labelstudio@example.com | labelstudio     |
| Airflow      | airflow@example.com     | airflow         |
| Grafana      | admin                   | admin           |
| MinIO        | your-access-key         | your-secret-key |

To access **Jupyter Notebook**, run the following command and look for the login URL:

```bash
docker logs jupyter
```
Look for
```
http://127.0.0.1:8888/lab?token=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```
Substitute `127.0.0.1` with the floating IP assigned to your instance to open the Jupyter Lab interface.

---

## 📂 **WIP Volumes and Data Persistence**

* `/app/models`: Mounted as read-only for model access.
* `minio_data`: Persistent volume for MinIO object storage.

---

## ❓ **Common Issues**

* If you encounter `network production_net not found`, it means you forgot to create the network. Please run:

  ```bash
  docker network create production_net
  # rebuild docker compose
  docker compose -f ./docker/backend/docker-compose-production.yml up --build -d
  ```

* If volume permission issues arise:

  ```bash
  sudo chown -R 1000:1000 /path/to/volume
  ```
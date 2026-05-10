# 🛡️ Autonomous Cyber Defense System (ACDS)

An intelligent, scalable, and autonomous cybersecurity framework that combines eBPF-based telemetry, Machine Learning, Large Language Models (LLMs), Graph-Based Threat Analysis, and Automated Response Mechanisms to detect, analyze, and mitigate modern cyber threats in real time.

---

# 🚀 Overview

Traditional cybersecurity systems rely heavily on static signatures and manual intervention, making them ineffective against evolving threats such as:

- 🦠 Zero-day attacks
- 🎯 Advanced Persistent Threats (APTs)
- 🔄 Lateral movement
- 🔐 Encrypted malicious traffic
- 🤖 Automated attack campaigns

The Autonomous Cyber Defense System (ACDS) addresses these limitations using a multi-layered architecture that continuously observes system behavior, performs intelligent threat detection, explains threats contextually using LLMs, visualizes attack paths, and automatically mitigates malicious activity.

---

# ✨ Key Features

## 📡 Real-Time Telemetry Collection

- eBPF-based kernel observability
- System call monitoring
- Network flow capture
- Process and container-level visibility

---

## 🧠 Hybrid Threat Detection Engine

### Supervised ML Models
- 🌲 Random Forest
- ⚡ XGBoost

### Unsupervised Anomaly Detection
- 🔍 Autoencoders
- 📈 Isolation Forests

### Ensemble Intelligence
- 🎯 Reduced false positives
- ⚖️ Better precision and recall
- 🚨 Detection of known + zero-day threats

---

## 🤖 LLM-Powered Threat Analysis

- 📝 Human-readable threat summaries
- 🔎 Root cause analysis
- ⚠️ Severity classification
- 💡 Automated mitigation recommendations

---

## 🕸️ Graph-Based Attack Analysis

- Neo4j-powered attack graph visualization
- 🔗 Multi-stage attack tracing
- 🛰️ Lateral movement detection
- 🧩 Relationship mapping between hosts and processes

---

## ⚔️ Automated Response Engine

- 🚫 IP blocking
- 🧱 Process/container isolation
- 📦 Traffic quarantine
- ⏱️ Rate limiting
- 👨‍💻 Human-in-the-loop override mechanism

---

## ☁️ Cloud-Native Deployment

- 🐳 Docker containerization
- ☸️ Kubernetes orchestration
- 📦 Scalable microservices architecture

---

# 🏗️ System Architecture

The ACDS pipeline consists of the following major layers:

1. 📥 Telemetry Collection Layer
2. 📡 Streaming & Message Bus
3. 🧪 Feature Engineering
4. 🧠 Hybrid ML Detection Engine
5. 🤖 LLM-Based Threat Analysis
6. ⚖️ Decision Engine
7. ⚔️ Automated Response Engine
8. 🕸️ Graph-Based Attack Analysis
9. ☁️ Deployment & Scalability Layer
10. 🔄 Continuous Learning Feedback Loop

---

# 🛠️ Tech Stack

## 💻 Backend & Infrastructure

- Python
- Apache Kafka
- Docker
- Kubernetes (k3s)
- Redis Streams

## 🔐 Cybersecurity & Observability

- eBPF
- Deep Packet Inspection (DPI)
- JA3 / JA3S TLS Fingerprinting

## 🧠 Machine Learning & AI

- Scikit-learn
- XGBoost
- Autoencoders
- ONNX Runtime
- Llama 3 / Mistral 7B

## 📊 Visualization & Graph Analytics

- Neo4j
- Grafana
- Prometheus

## 🌐 Frontend

- React
- Vite

---

# 📂 Project Structure

```bash
ACDS/
│
├── backend/
│   ├── telemetry/
│   ├── kafka/
│   ├── feature_engineering/
│   ├── ml_detection/
│   ├── llm_analysis/
│   ├── response_engine/
│   └── graph_engine/
│
├── frontend/
│
├── models/
│   ├── random_forest/
│   ├── xgboost/
│   ├── autoencoder/
│   └── isolation_forest/
│
├── deployment/
│   ├── docker/
│   └── kubernetes/
│
├── datasets/
│
├── scripts/
│
└── README.md
```

---

# 📊 Dataset

The ML models were trained and evaluated using the CICIDS2017 dataset.

### Dataset Includes

- 📈 2.8+ million traffic samples
- 🎯 15 attack categories
- 🔐 Benign and malicious traffic patterns

---

# ⚙️ Installation & Setup

## ✅ Prerequisites

Ensure the following are installed:

- 🐳 Docker
- ☸️ Kubernetes / k3s
- 🐍 Python 3.10+
- 🌐 Node.js
- 📡 Apache Kafka
- 🕸️ Neo4j

---

## 📥 Clone the Repository

```bash
git clone https://github.com/your-username/acds.git
cd acds
```

---

## 🖥️ Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

---

## 🌐 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## 📡 Run Kafka

```bash
docker-compose up kafka
```

---

## 🕸️ Run Neo4j

```bash
docker-compose up neo4j
```

---

## 🧠 Start the ML Detection Service

```bash
python ml_detection/main.py
```

---

## 🤖 Start the LLM Analysis Service

```bash
python llm_analysis/main.py
```

---

## 🐳 Deploy Using Docker

```bash
docker-compose up --build
```

---

## ☸️ Kubernetes Deployment

```bash
kubectl apply -f deployment/kubernetes/
```

---

# 📈 Experimental Results

| 📌 Metric | ✅ Result |
|---|---|
| Random Forest Precision | 98.4% |
| Random Forest Recall | 97.9% |
| Zero-Day Detection F1-Score | 94.2% |
| False Positive Rate | 1.2% |
| Mean Time to Response (MTTR) | 2.8s |
| LLM Summary Accuracy | 92% |

---

# 🧪 Testing

Testing included:

- ✅ Unit Testing
- 🔗 Integration Testing
- ⚙️ End-to-End Pipeline Validation
- 📊 Load Testing
- 🎯 Attack Simulation

## 🛠️ Tools Used

- pytest
- Scapy
- tcpreplay
- Locust
- Grafana
- Prometheus
- Neo4j Browser

---

# 🔮 Future Enhancements

- 🪟 Windows eBPF support
- 🏢 SIEM integration (Splunk, Elastic SIEM)
- 🤝 Federated Learning
- 🔄 Online continual learning
- ⚡ Autonomous remediation playbooks
- 📊 Advanced SOC dashboard improvements

---

# 👨‍💻 Team Members

| 👤 Member | 🎯 Role |
|---|---|
| Naomi Andrea Pereira | LLM Integration Lead |
| Pranav M. K. | Telemetry & Infrastructure Lead |
| Pranav Sreeharsha | ML/DL Detection Lead |
| Prapti Ramachandra Nayak | DPI, Graph Analysis & Response Lead |

---

# 🎓 Guided By

Mrs. Shanmuga Priya R.  
Assistant Professor, Department of ISE

---

# 📜 License

This project is developed for academic and research purposes under Ramaiah Institute of Technology.

---

# 🙏 Acknowledgement

We sincerely thank the Department of Information Science & Engineering, Ramaiah Institute of Technology, for the support and guidance provided throughout the development of this project.

# 🛒 SenseMart V1 – Smart IoT Vending Machine

<p align="center">

## Intelligent IoT-Based Smart Vending Machine using Python, Flask, Firebase & ESP32

An end-to-end smart vending machine that combines IoT hardware with cloud technologies to automate inventory management, product purchasing, and real-time monitoring.

</p>

---

## 📖 Project Overview

SenseMart V1 is a smart vending machine system developed using **Python**, **Flask**, **Firebase**, and **ESP32**.

The project integrates a web application with IoT hardware to provide an automated vending experience for customers while allowing administrators to manage inventory, pricing, and transactions through a secure dashboard.

The system supports **voice-assisted product selection**, **real-time inventory updates**, **weight sensor verification**, and **cloud synchronization**, making it suitable for modern automated retail environments.

---

# ✨ Features

## 👤 Customer Features

- Browse available products
- Voice-assisted product selection
- Product search
- QR Code payment support
- Product recommendations
- Real-time stock availability

---

## 👨‍💼 Administrator Features

- Secure Admin Login
- Inventory Management
- Product Management
- Dynamic Pricing
- Transaction Logs
- Product Image Upload
- Analytics Dashboard

---

## 🌐 IoT Features

- ESP32 Integration
- HX711 Weight Sensor
- Firebase Cloud Synchronization
- Serial Communication
- Automatic Inventory Updates

---

# 🏗 System Architecture

<p align="center">
<img src="docs/screenshots/architecture.jpg" width="900">
</p>

The system consists of:

- Customer Interface
- Voice Recognition Module
- Flask Backend
- Firebase Cloud Database
- ESP32 IoT Controller
- Weight Sensor
- Dynamic Pricing Module
- Administrator Dashboard

---

# 📸 Project Screenshots

## 🏠 Customer Home

Customers can browse products, search products manually, or use voice commands for product selection.

<p align="center">
<img src="docs/screenshots/home.jpg" width="900">
</p>

---

## 🛒 Product Purchase

Displays product details, pricing, recommendations, and purchase confirmation.

<p align="center">
<img src="docs/screenshots/product.jpg" width="900">
</p>

---

## 🔐 Admin Login

Secure administrator authentication.

<p align="center">
<img src="docs/screenshots/admin_login.jpg" width="700">
</p>

---

## 📊 Admin Dashboard

Manage inventory, products, pricing, transaction logs, and system settings.

<p align="center">
<img src="docs/screenshots/admin_panel.jpg" width="900">
</p>

---

## ✏ Product Management

Administrators can modify:

- Product Name
- Price
- Stock Quantity
- Product Weight
- Product Images

<p align="center">
<img src="docs/screenshots/update_product.jpg" width="900">
</p>

---

# ⚙ Technology Stack

| Category | Technologies |
|------------|---------------------------|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | Firebase Firestore, SQLite |
| IoT Hardware | ESP32 |
| Sensors | HX711 Load Cell |
| Communication | Serial Communication |
| Version Control | Git, GitHub |

---

# 🔄 System Workflow

```text
                    Customer
                        │
                        ▼
              Flask Web Application
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
 Voice Commands    Firebase Cloud   Admin Dashboard
        │               │
        └───────────────┘
                │
                ▼
          ESP32 Controller
                │
                ▼
      Weight Sensor (HX711)
                │
                ▼
      Inventory Verification
                │
                ▼
     Real-Time Database Update
```

---

# 📂 Project Structure

```text
SenseMart-V1/
│
├── app.py
├── firebase_config.py
├── firebase_db.py
├── requirements.txt
│
├── templates/
│
├── static/
│
├── esp32_example/
│
├── docs/
│   └── screenshots/
│
└── README.md
```

---

# 🚀 Installation

Clone the repository

```bash
git clone https://github.com/abhinav7860/New_Vending_Machine.git
```

Move into the project

```bash
cd New_Vending_Machine
```

Create a virtual environment

```bash
python -m venv venv
```

Activate it

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run the application

```bash
python app.py
```

Open

```
http://127.0.0.1:5000
```

---

# 🔌 Hardware Requirements

- ESP32 Development Board
- HX711 Load Cell Amplifier
- Load Cell
- USB Serial Communication

Upload

```
esp32_example/esp32_weight_example.ino
```

to the ESP32 before running the project.

---

# 🔑 Default Admin Credentials

**Username**

```
admin
```

**Password**

```
admin123
```

> **Note:** Change the default credentials before deploying the application.

---

# 🚀 Future Improvements

- AI Product Recommendation
- Mobile Application
- UPI Payment Integration
- Face Recognition Authentication
- Cloud Monitoring Dashboard
- Predictive Inventory Management
- Sales Analytics using Machine Learning

---

# 👨‍💻 Developer

**Abhinav Sabu**

**B.Tech Computer Science & Engineering**

GitHub: https://github.com/abhinav7860

LinkedIn: *(Add your LinkedIn profile here)*

---

## ⭐ Support

If you found this project useful, consider giving it a **⭐ Star** on GitHub.

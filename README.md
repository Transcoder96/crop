

Agri-Advisor — Smart Crop Recommendation System

A full-stack IoT + Data-driven agricultural advisory platform that analyzes soil, weather, and seasonal data to recommend the most suitable crops with profit estimation.

---

## System Preview

The system provides a smart dashboard built using Streamlit where farmers can input soil data and view real-time recommendations.
It integrates hardware sensor readings and environmental conditions to generate accurate crop suggestions.

The interface includes live monitoring, crop ranking, fertilizer recommendations, and downloadable PDF reports for field use.

---

## Overview

Agri-Advisor is an intelligent farming assistant designed to help farmers make data-driven decisions.

It combines soil nutrients, environmental conditions, rainfall data, and seasonal patterns to recommend the best crops for cultivation.

The system also estimates yield, revenue, cost, and net profit, making it both a scientific and economic decision tool.

---

## Core Features

The platform provides crop recommendations based on soil NPK values, temperature, moisture, and rainfall.

It evaluates crops using a scoring engine that considers nutrient compatibility, environmental conditions, and seasonal suitability.

It generates ranked crop lists along with risk levels, expected yield, and profitability.

It includes fertilizer recommendations based on nutrient gaps for the selected crop.

It provides intercropping suggestions and government schemes relevant to the crop.

It generates professional PDF reports for farmers with complete analysis.

---

## System Architecture

User interacts with the Streamlit dashboard to input soil and environmental data.
The backend processing engine evaluates multiple crops using scoring algorithms.
The system uses predefined crop datasets including nutrient requirements and growth conditions.
Results are processed and displayed as rankings, insights, and recommendations.
PDF reports are generated using ReportLab for offline usage.

---

## Data Flow

User enters land size, soil nutrients, and environmental parameters.
Sensor data can be fetched from Arduino via serial communication.
The system processes input through a scoring engine.
Each crop is evaluated and ranked based on compatibility.
Results are displayed with profitability and risk insights.
A detailed report can be generated and downloaded.

---

## Tech Stack

Frontend uses Streamlit for interactive UI.
Backend logic is implemented in Python.
Data processing uses Pandas.
Hardware communication uses PySerial.
Report generation uses ReportLab.
QR codes are generated using QRCode library.

---

## Project Structure

app.py

Arduino code handles sensor data collection and serial transmission

The system contains embedded crop datasets, scoring logic, and report generator within the main application

---

## Installation

Install dependencies:

pip install streamlit pandas pyserial reportlab qrcode

Run the application:

streamlit run app.py

---

## Hardware Integration

The system supports Arduino-based sensors for real-time data collection.

Sensors measure temperature, humidity, soil moisture, and sunlight.

Data is transmitted via serial communication and averaged over time for accuracy.

Manual override is also available for testing without hardware.

---

## Core Logic

The scoring engine evaluates crops based on three main factors:

NPK compatibility score
Temperature and moisture score
Seasonal and rainfall suitability

Final score is calculated using weighted averages and penalties for off-season or unsuitable rainfall.

Risk level is categorized as Low, Medium, or High based on final score.

---

## Crop Intelligence

The system includes a dataset of multiple crop categories including grains, pulses, oilseeds, vegetables, and fruits.

Each crop contains detailed parameters such as nutrient requirements, growth duration, water needs, expected yield, and market price trends.

It also maps crops to nearby mandi markets and government schemes.

---

## Output Insights

Crop ranking based on suitability percentage
Expected yield and revenue estimation
Input cost and net profit calculation
Fertilizer requirement based on soil deficiency
Intercropping suggestions
Government schemes eligibility
Season-based recommendations

---

 Impact

The system helps farmers choose the most profitable and suitable crop based on scientific data.

It reduces guesswork in farming decisions and improves productivity.

It bridges the gap between agriculture and technology using IoT and analytics.

---

 Future Scope

Integration with mobile applications
Real-time weather API integration
AI-based crop prediction models
Cloud database for large-scale deployment
Multi-language farmer interface

---

 Author

Surya Prakash Jha
Agri-Advisor Project — 2026

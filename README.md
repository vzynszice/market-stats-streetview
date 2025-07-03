# Market Statistics Extraction from Google Street View

This repo contains the data collection script we developed to detect **exterior features** of small markets (fruit and vegetable section, beverage cabinet, ice cream cabinet, chip section, signboard) from Google Street View images, the YOLO v8‑v12 and RT‑DETR training notebook, the experiment results, and the project report.


## Setup
git clone https://github.com/vzynszice/market-stats-streetview.git

cd market-stats-streetview

python -m venv venv && source venv/bin/activate    

pip install -r requirements.txt

### API KEY
Get a GOOGLE_API_KEY from Google Cloud Services 

GOOGLE_API_KEY=YOUR_KEY_HERE

## 1. Data Collection

python src/data_collection.py --lat 41.0263 --lng 28.8767 --radius_km 10

## 2. Model Training

By following the steps in the notebook, you can train the YOLO models and the RT-DETR model for 50 epochs.




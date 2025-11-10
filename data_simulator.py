import time              
import random             
from datetime import datetime  
from database import insert_reading, init_db  

def generate_temperature():
    # Simulate temperature between 20–80 °C (float) 
    return round(random.uniform(20.0, 80.0), 2)  # 2 decimals for readability 

def generate_pressure():
    # Simulate pressure between 1–10 bar (float) 
    return round(random.uniform(1.0, 10.0), 2)   # 2 decimals 

def generate_motor_speed():
    # Simulate motor speed between 500–3000 RPM (int) 
    return random.randint(500, 3000)             # whole number RPM 

def iso_now():
    # Current time in ISO 8601 (e.g., 2025-10-05T09:36:00) 
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"  # 'Z' to mark UTC 

def main():
    init_db()  # ensure table exists before inserting 
    print("Starting simulator. Press Ctrl+C to stop.")  # status message 
    try:
        while True:  # infinite loop to generate a reading per second 
            ts = iso_now()                   # timestamp string 
            temp = generate_temperature()    # random temp 
            pres = generate_pressure()       # random pressure 
            rpm = generate_motor_speed()     # random rpm 
            insert_reading(ts, temp, pres, rpm)  # save to SQLite 
            print(f"{ts} | T={temp}°C P={pres}bar RPM={rpm}")  # quick console log 
            time.sleep(1)  # wait 1 second before next reading 
    except KeyboardInterrupt:
        print("Simulator stopped.")   

if __name__ == "__main__":
    main()   

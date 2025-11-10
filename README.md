# Industrial AI Anomaly Detection Dashboard

This project is a real-time monitoring dashboard that keeps an eye on industrial sensor data and uses machine learning to spot any unusual behavior. The backend is a simple Flask app that provides data, and the frontend is a clean, single-page interface built with vanilla JavaScript and Plotly.js for the charts.

It's designed to be straightforward to get up and running, whether you want to play with it on your local machine or deploy it using Docker.



<img width="1919" height="895" alt="Screenshot 2025-11-10 213750" src="https://github.com/user-attachments/assets/09006b60-ce27-4450-b4ea-da6531f6a0b0" />



<img width="1919" height="896" alt="Screenshot 2025-11-10 213817" src="https://github.com/user-attachments/assets/09144d1c-07c5-4a8e-ae50-fe903bac97a2" />


<img width="1917" height="893" alt="Screenshot 2025-11-10 213833" src="https://github.com/user-attachments/assets/9ca14a6f-47f9-47ff-8fe5-3ce24a8ca476" />


<img width="1917" height="895" alt="Screenshot 2025-11-10 213847" src="https://github.com/user-attachments/assets/17005777-0488-4f39-a847-6e22be0d720a" />


<img width="1918" height="895" alt="Screenshot 2025-11-10 213934" src="https://github.com/user-attachments/assets/de1f7bb4-80d8-4b16-ba4c-2149b4b8d07e" />



## What's Cool About It?

*   **Live Charts**: A sleek dashboard that shows key sensor readings like Temperature, Pressure, and RPM. The charts auto-refresh and scroll smoothly, giving you that satisfying "Mission Control" feel.
*   **Smart Anomaly Spotting**: It's got two different brains for catching weird data points:
    *   **Isolation Forest**: A fast and reliable model that's great for spotting outliers right away.
    *   **LSTM Autoencoder**: A more advanced deep learning model that you can train to learn the normal rhythm of your data and flag anything that breaks the pattern.
*   **A Fun, Interactive UI**:
    *   You can get a high-level overview or dive deep into the charts for each individual sensor.
    *   Play around with the model settings, like the "contamination" factor, and see how it changes the anomalies that get flagged.
    *   Check out a clean, sortable table of all the anomalies that have been detected.
*   **Time Travel is Real (Sort of)**:
    *   **Live Mode**: See what's happening on your sensors right this second.
    *   **Replay Mode**: Jump back in time to review historical data. You can play, pause, step through the timeline, or even zap to a specific date and time to investigate an event.
*   **Get Your Data Out**:
    *   Easily download the full table of anomalies as a CSV file.
    *   Generate a slick, printable PDF report for any time period you choose.
*   **Runs Anywhere with Docker**: The whole setup is containerized, so you can spin it up with a single command without worrying about dependencies.

## How to Get It Running

### The Fast Track (with Docker)

If you've got Docker, this is the easiest way to go. The `docker-compose.yml` file handles everything, setting up both the web app and a data simulator to give it a live feed.

1.  **Build and run the containers:**
    ```
    docker-compose up --build
    ```

That's it, you're done! The dashboard will be up and running at `http://localhost:5000`. The database is stored in a Docker volume, so your data won't disappear when you stop the containers.

### The Hands-On Local Setup

If you want to run the project directly on your machine to tinker with the code.

**1. Get your environment ready:**

First, grab the code and hop into the project folder.
```
git clone https://github.com/Jeevansai-01/Industrial-AI-Dashboard.git

cd Industrial-AI-Dashboard
```
Next, set up a Python virtual environment. It's like giving the project its own private little sandbox to play in, so its dependencies don't mess with your other Python projects.
```
On Windows
python -m venv .venv
..venv\Scripts\activate

On macOS or Linux
python3 -m venv .venv
source .venv/bin/activate
```


**2. Install all the things:**

Use pip to install all the Python packages the project needs.

```
pip install -r requirements.txt
```


**3. Set up the database:**

The dashboard needs some data to show. This command will create the database and fill it with some sample historical data so you have something to look at right away.
```
python cli.py start 

python cli.py stop

python cli.py status
```


**4. Go live!**

You're all set. Start the Flask development server.
```
flask run  
   or  
python app.py
```


Your dashboard is now live and waiting for you at `http://127.0.0.1:5000`.

If you want to simulate a live stream of new sensor data, open up a second terminal and run the simulator script:
```
python data_simulator.py
```


## How It's Made

This project brings together a few cool technologies in a way that's powerful but still easy to understand.

*   **Backend**: Flask (Python)
*   **Database**: SQLite
*   **Frontend**: Plain old JavaScript (ES6+), HTML5, and CSS3
*   **Charts**: Plotly.js
*   **Machine Learning**: Scikit-learn (for the Isolation Forest) and TensorFlow/Keras (for the LSTM)
*   **Deployment**: Docker & Docker Compose
*   **Code Style**: I used `black`, `ruff`, and `pytest` to keep the code looking sharp and working correctly.

## Running the Tests

I've written a bunch of tests to make sure everything is running smoothly. You can run them yourself with:
```
pytest
```



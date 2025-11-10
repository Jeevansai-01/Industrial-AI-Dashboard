import numpy as np
from keras.models import Model, load_model
from keras.layers import Input, LSTM, RepeatVector, TimeDistributed, Dense
from sklearn.preprocessing import StandardScaler
import joblib, os


HERE = os.path.dirname(__file__)
DEFAULT_ART_DIR = os.path.abspath(os.path.join(HERE, "..", "artifacts"))

def build_lstm_autoencoder(n_feats, seq_len, latent=32):
    inp = Input(shape=(seq_len, n_feats))
    x = LSTM(latent, return_sequences=False)(inp)
    x = RepeatVector(seq_len)(x)
    x = LSTM(latent, return_sequences=True)(x)
    out = TimeDistributed(Dense(n_feats))(x)
    model = Model(inp, out)
    model.compile(optimizer="adam", loss="mse")
    return model

def make_sequences(X, seq_len):
    # X: [N, F] newest-first or oldest-first; assume oldest->newest
    xs = []
    for i in range(len(X)-seq_len+1):
        xs.append(X[i:i+seq_len])
    return np.array(xs)  # [N-seq+1, seq_len, F]

def train_and_save(X, seq_len=24, epochs=20, batch_size=64, artifacts_dir="./artifacts"):
    os.makedirs(artifacts_dir, exist_ok=True)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    S = make_sequences(Xs, seq_len)
    model = build_lstm_autoencoder(n_feats=X.shape[1], seq_len=seq_len)
    model.fit(S, S, epochs=epochs, batch_size=batch_size, verbose=0, shuffle=True)
    model.save(os.path.join(artifacts_dir, "lstm.keras"))
    joblib.dump({"scaler": scaler, "seq_len": seq_len}, os.path.join(artifacts_dir, "lstm_meta.pkl"))

def load_artifacts(artifacts_dir="./artifacts"):
    meta = joblib.load(os.path.join(artifacts_dir, "lstm_meta.pkl"))
    model = load_model(os.path.join(artifacts_dir, "lstm.keras"))
    return model, meta["scaler"], meta["seq_len"]

def score_sequences(model, S):
    # ensure inference mode
    R = model.predict(S, verbose=0, use_multiprocessing=False)
    err = np.mean((S - R)**2, axis=(1,2))
    return err

#!/usr/bin/env bash

# Install system dependencies for audio processing
apt-get update
apt-get install -y ffmpeg

# Gradio's pydub dependency sometimes needs additional libraries.
# Although ffmpeg usually covers it, these can be helpful for other cases.
# apt-get install -y libsndfile1 portaudio19-dev python3-pyaudio

# Now install Python dependencies
pip install -r requirements.txt

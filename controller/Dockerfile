FROM balenalib/raspberrypi3-debian-python:3.11-bookworm-build

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y python3-lgpio swig liblgpio-dev \
    && pip install --no-cache-dir phatbeat gpiozero rpi-lgpio requests redis

COPY . .

CMD ["python", "controller.py"]

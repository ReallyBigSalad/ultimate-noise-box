FROM balenalib/raspberrypi3-debian-python:3.11-bookworm-build

RUN sed -i 's|deb.debian.org|archive.debian.org|g' /etc/apt/sources.list \
    && sed -i 's|security.debian.org|archive.debian.org|g' /etc/apt/sources.list \
    && sed -i '/buster-updates/d' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y python3-pygame

RUN pip3 install Flask-API "Werkzeug==2.3.7" "Flask==2.3.3"

# Tested versions:
# flask 2.0.2
# Flask-API 3.0.post1

WORKDIR /usr/src/app

COPY *.py ./
COPY *.sh ./
COPY ./assets ./assets


CMD [ "bash", "start.sh" ]

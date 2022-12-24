FROM python:3.10.8

RUN \
  apt-get update \
  # && apt-get install --no-install-recommends -y some-pkg \
  && pip3 install --no-cache-dir --upgrade pip \
  && rm -rf /var/lib/apt/lists/*

ADD requirements/requirements-prod.txt /requirements/

RUN pip3 install --no-cache-dir -r /requirements/requirements-prod.txt

ENV APP_DIR /botwit
WORKDIR $APP_DIR
ADD . $APP_DIR

RUN pip install --editable .

CMD ["botwit", "serve", "--host", "0.0.0.0", "--port", "8000"]

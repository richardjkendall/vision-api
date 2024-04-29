FROM python:3.12-slim

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0

ADD requirements.txt .
ADD *.py .
RUN pip install -r requirements.txt

CMD [ "gunicorn", "--timeout", "600", "--bind", "0.0.0.0:8000", "-w", "4", "api:app" ]
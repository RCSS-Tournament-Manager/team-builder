FROM python:3.11-buster AS builder

WORKDIR /app

# RUN python -m venv /app/venv
# ENV PATH="/app/venv/bin:$PATH"

# RUN pip install --trusted-host pypi.python.org --upgrade pip setuptools wheel
# COPY requirements.txt /app
# RUN pip install --trusted-host pypi.python.org -r /app/requirements.txt

# COPY ./calculation-service.py /app/
# COPY ./src /app/src

# CMD ["python", "-u", "builder.py"]

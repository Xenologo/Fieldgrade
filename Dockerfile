# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Base deps first for better layer caching
COPY requirements.txt ./
COPY termite_fieldpack/requirements.txt termite_fieldpack/requirements.txt
COPY mite_ecology/requirements.txt mite_ecology/requirements.txt
COPY fieldgrade_ui/requirements.txt fieldgrade_ui/requirements.txt

RUN python -m pip install -U pip \
  && python -m pip install -r requirements.txt

# Install packages (editable so entrypoints + imports are consistent)
COPY termite_fieldpack/ termite_fieldpack/
COPY mite_ecology/ mite_ecology/
COPY fieldgrade_ui/ fieldgrade_ui/
COPY schemas/ schemas/
COPY resources/ resources/
COPY pytest.ini Makefile README.md WINDOWS.md TERMUX.md ./

RUN python -m pip install -e termite_fieldpack \
  && python -m pip install -e mite_ecology \
  && python -m pip install -e fieldgrade_ui

EXPOSE 8787

# Default command is overridden by compose for web/worker
CMD ["python", "-m", "fieldgrade_ui", "serve"]

FROM python:3.7

ENV PIP_DISABLE_PIP_VERSION_CHECK=on
RUN pip install poetry

WORKDIR /src
COPY poetry.lock pyproject.toml /src/
RUN poetry config settings.virtualenvs.create false
RUN poetry install --no-interaction

COPY . /src

CMD kopf run /src/aws.py /src/handlers.py --verbose --standalone

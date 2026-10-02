# The service's image: Python + our code + its libraries. The AI model is not inside (see README).
# Steps run from rarely changing to often changing, so a code edit only redoes the last steps.
FROM python:3.13-slim

WORKDIR /app

# An ordinary user to run the service as (created early: it never changes)
RUN useradd --create-home appuser

# Libraries next: this step is only redone when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Our code last: it changes most often
COPY app ./app

# Run as that ordinary user, not root: if the service were ever compromised, the attacker
# could not change our code, the installed libraries or the system's files (only this user's own home folder)
USER appuser

EXPOSE 8000
# --host 0.0.0.0: accept requests from outside the container, not only from inside it
CMD ["uvicorn", "app.edges.api:app", "--host", "0.0.0.0", "--port", "8000"]

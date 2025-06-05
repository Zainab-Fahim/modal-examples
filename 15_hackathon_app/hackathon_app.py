# ---
# cmd: ["modal", "serve", "15_hackathon_app/hackathon_app.py"]
# deploy: true
# ---

# # Hackathon submission app
#
# This example shows how to build a simple hackathon submission portal using Modal.
# We expose a small FastAPI web server where teams can POST their projects and
# list existing submissions. Every submission is also sent to a Slack channel
# using a bot token stored in a Modal secret. This demonstrates Modal's web
# serving, secrets handling and persistent storage features.

import os
from typing import List

import modal
from fastapi import FastAPI
from pydantic import BaseModel

# Define a Modal image with the packages we need for the FastAPI server and Slack
# integration. We pin versions to keep the example deterministic.
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi[all]~=0.111.0", "pydantic~=2.7.3", "slack-sdk~=3.27.1"
)

app = modal.App("example-hackathon-app", image=image)

# We store submissions in a persistent modal.Dict so that they survive restarts.
submissions = modal.Dict.from_name("hackathon-submissions", create_if_missing=True)


# Slack posting helper. Requires a secret with a `SLACK_BOT_TOKEN` key.
@app.function(
    secrets=[
        modal.Secret.from_name("hackathon-slack", required_keys=["SLACK_BOT_TOKEN"])
    ]
)
def post_to_slack(message: str):
    import slack_sdk

    client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(channel="hackathon-submissions", text=message)


# Define the FastAPI app and endpoints
web_app = FastAPI()


class Submission(BaseModel):
    team: str
    project: str
    description: str | None = None


@web_app.post("/submit")
async def submit(submission: Submission):
    submissions[submission.team] = submission.model_dump()
    post_to_slack.remote(f"New submission from {submission.team}: {submission.project}")
    return {"status": "received"}


@web_app.get("/projects", response_model=List[Submission])
async def list_projects():
    return [Submission(**data) for data in submissions.values()]


@app.function()
@modal.asgi_app()
def fastapi_app():
    return web_app

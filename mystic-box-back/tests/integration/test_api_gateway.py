import os

import boto3
import pytest
import requests

"""
Make sure env variable AWS_SAM_STACK_NAME exists with the name of the stack we are going to test. 
"""


class TestApiGateway:

    @pytest.fixture()
    def stack_outputs(self):
        """ Get the Cloudformation Stack outputs """
        stack_name = os.environ.get("AWS_SAM_STACK_NAME")

        if stack_name is None:
            raise ValueError('Please set the AWS_SAM_STACK_NAME environment variable to the name of your stack')

        client = boto3.client("cloudformation")

        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name} \n" f'Please make sure a stack with the name "{stack_name}" exists'
            ) from e

        stacks = response["Stacks"]
        return {output["OutputKey"]: output["OutputValue"] for output in stacks[0]["Outputs"]}

    def test_get_random_cards(self, stack_outputs):
        """ Call the random cards endpoint and check the response """
        response = requests.get(stack_outputs["GetRandomCardsApi"])

        assert response.status_code == 200
        assert response.json() == {"cards": []}

    def test_get_user_cards(self, stack_outputs):
        """ Call the user cards endpoint and check the response """
        url = stack_outputs["GetUserCardsApi"].replace("{userId}", "test-user")
        response = requests.get(url)

        assert response.status_code == 200
        assert response.json() == {"cards": []}

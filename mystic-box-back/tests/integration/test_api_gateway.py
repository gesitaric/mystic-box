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

    def test_open_box(self, stack_outputs):
        """ Call the open box endpoint and check the response """
        response = requests.post(stack_outputs["OpenBoxApi"])

        assert response.status_code == 200
        cards = response.json()["cards"]
        assert len(cards) == 1
        assert set(cards[0]) == {"name", "rarity", "file_name"}

    def test_get_user_cards_requires_authentication(self, stack_outputs):
        """ The user cards endpoint must reject anonymous requests """
        response = requests.get(stack_outputs["GetUserCardsApi"])

        assert response.status_code == 401

    def test_save_user_card_requires_authentication(self, stack_outputs):
        """ The save card endpoint must reject anonymous requests """
        response = requests.post(stack_outputs["SaveUserCardApi"], json={})

        assert response.status_code == 401

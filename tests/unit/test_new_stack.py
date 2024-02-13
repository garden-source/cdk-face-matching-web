import aws_cdk as core
import aws_cdk.assertions as assertions

from new.new_stack import NewStack

# example tests. To run these tests, uncomment this file along with the example
# resource in new/new_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = NewStack(app, "new")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })

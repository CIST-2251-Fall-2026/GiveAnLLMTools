# Small Store Tool-Calling Assistant

This Python application lets a locally running language model use ordinary Python functions as tools for a fictional small grocery and household goods store. The model decides whether it can answer a question itself or needs a tool and it requests those tools through Ollama's structured tool_calls data rather than through ordinary text.

## Setup

1. Install Ollama from ollama.com/download and make sure it is running.
2. Download the model with `ollama pull qwen3:4b`.
3. Install the Ollama Python package with `python -m pip install ollama`.
4. From this folder, run `python app.py`.

This project uses the qwen3:4b model. My computer ran it on the CPU, so no substitution to qwen3:1.7b was needed, though each answer takes a few minutes.

## Files

- `app.py` contains the tools, tool descriptions, validation, error handling, control loop, logging and tests.
- `products.json` holds fictional, non-sensitive product data (rice, milk, coffee and bleach with prices in cents, sizes and units).
- `interaction_log.jsonl` is the log from the final test run, with one interaction per line.

## Tools

- `lookup_product` reads products.json and returns a product's price in cents, package size and unit.
- `order_total` calculates the total cost in cents for a quantity of one product.
- `convert_units` converts pounds to kilograms, gallons to liters, or ounces to grams.

Each tool is described with a JSON schema that gives its name, a description and the type and allowed values of each argument.

## How it works

The `ask` function sends the question and the tool descriptions to qwen3:4b. If the model's reply contains structured tool_calls, the application validates each requested tool and its arguments, runs the approved function and sends the result back to the model in a tool message. The model then uses that result to write its final answer. If the reply has no tool calls, that reply is the final answer. The loop allows at most three rounds of tool calls.

## Validation and error handling

Before any function runs, `validate_call` checks that the tool name is in the approved registry, that exactly the required arguments are present, that product names and units are allowed values, that the quantity is a whole number from 1 through 100 and that the amount is a number. The `run_tool` function catches invalid requests and failed functions and returns an error message instead of crashing. Each model call also has a five-minute timeout, so a stuck question is recorded and skipped instead of freezing the program.

These checks prevent several customer risks. The model can never run an unknown or made-up function, so it cannot reach code the business did not approve. Unchecked arguments such as text quantities, true or false values, unknown products, or quantities over 100 never reach the business code. A tool that fails, such as an unsupported unit conversion, reports an error instead of stopping the application and a slow model reply cannot hang the assistant forever.

## Logging

Every interaction is saved to interaction_log.jsonl with the original request, each selected tool, its arguments, the tool result and the final answer.

## Test results

The final run is saved in interaction_log.jsonl.

- "Look up the price of coffee." used lookup_product and returned 899 cents for 12 ounces.
- "How much do 3 bags of rice cost?" used order_total and returned $14.97.
- "Convert 5 pounds to kilograms." used convert_units and returned 2.27 kilograms.
- "What day comes after Monday?" used no tool. However, the model said it could not answer instead of saying Tuesday and part of its reasoning appeared in the answer.
- "How much do 500 bags of rice cost?" timed out after five minutes and the timeout was handled and logged.
- A scripted request for an unknown tool, delete_inventory, was rejected as an unknown tool.
- A scripted order_total request with the quantity "three" was rejected as an invalid argument.

The two scripted requests were sent directly to run_tool, since the model only chooses from the three approved tools and does not reliably produce an invalid tool name on its own. Earlier test runs also showed that a question about 4 gallons of milk timed out repeatedly.

## AI assistance

I used Claude as a step-by-step tutoring guide for this project. Claude planned the steps from the assignment requirements, explained each Python term before I used it and provided the code, which I typed and ran myself in VS Code. Claude also helped me debug problems along the way, including the model's thinking text appearing in answers, which was fixed by setting think=True and a question that hung, which led to adding the timeout. I chose the business scenario, created the files, ran every test and checked each result.

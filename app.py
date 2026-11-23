import json
import ollama
import httpx


def lookup_product(name):
    """Look up one product in products.json and return its price, size, and unit."""
    with open("products.json") as file:
        products = json.load(file)
    product = products[name]
    return {"product": name, "price_cents": product["price_cents"],
            "size": product["size"], "unit": product["unit"]}


def order_total(name, quantity):
    """Calculate the total cost in cents for a quantity of one product."""
    price = lookup_product(name)["price_cents"]
    return {"product": name, "quantity": quantity, "total_cents": price * quantity}


def convert_units(amount, from_unit, to_unit):
    """Convert an amount from one unit to another."""
    conversions = {
        ("pounds", "kilograms"): 0.453592,
        ("gallons", "liters"): 3.78541,
        ("ounces", "grams"): 28.3495,
    }
    factor = conversions[(from_unit, to_unit)]
    return {"amount": amount, "from_unit": from_unit, "to_unit": to_unit,
            "result": round(amount * factor, 2)}


tools = [
    {"type": "function", "function": {
        "name": "lookup_product",
        "description": "Look up a store product and return its price in cents, package size, and unit.",
        "parameters": {"type": "object",
            "properties": {
                "name": {"type": "string", "enum": ["rice", "milk", "coffee", "bleach"],
                         "description": "The product name."}},
            "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "order_total",
        "description": "Calculate the total cost in cents for a quantity of one store product.",
        "parameters": {"type": "object",
            "properties": {
                "name": {"type": "string", "enum": ["rice", "milk", "coffee", "bleach"],
                         "description": "The product name."},
                "quantity": {"type": "integer",
                             "description": "How many to buy, a whole number from 1 through 100."}},
            "required": ["name", "quantity"]}}},
    {"type": "function", "function": {
        "name": "convert_units",
        "description": "Convert an amount from pounds to kilograms, gallons to liters, or ounces to grams.",
        "parameters": {"type": "object",
            "properties": {
                "amount": {"type": "number", "description": "The amount to convert."},
                "from_unit": {"type": "string", "enum": ["pounds", "gallons", "ounces"],
                              "description": "The unit to convert from."},
                "to_unit": {"type": "string", "enum": ["kilograms", "liters", "grams"],
                            "description": "The unit to convert to."}},
            "required": ["amount", "from_unit", "to_unit"]}}},
]

registry = {
    "lookup_product": lookup_product,
    "order_total": order_total,
    "convert_units": convert_units,
}


def validate_call(name, arguments):
    """Check the tool name and arguments before running anything."""
    if name not in registry:
        raise ValueError("Unknown tool: " + str(name))
    for tool in tools:
        if tool["function"]["name"] == name:
            schema = tool["function"]["parameters"]
    if not isinstance(arguments, dict) or set(arguments) != set(schema["required"]):
        raise ValueError("Missing or extra argument")
    for key, rule in schema["properties"].items():
        value = arguments[key]
        if rule["type"] == "string":
            if not isinstance(value, str) or value not in rule["enum"]:
                raise ValueError("Invalid value for " + key)
        elif rule["type"] == "integer":
            if type(value) is not int or not 1 <= value <= 100:
                raise ValueError("Quantity must be a whole number from 1 through 100")
        elif rule["type"] == "number":
            if type(value) not in (int, float):
                raise ValueError("Amount must be a number")
    return True


def run_tool(name, arguments):
    """Validate a tool request, run it, and return the result or an error."""
    try:
        validate_call(name, arguments)
        return registry[name](**arguments)
    except ValueError as error:
        return {"error": "Invalid request: " + str(error)}
    except (KeyError, TypeError) as error:
        return {"error": "Tool failed: " + str(error)}


MODEL = "qwen3:4b"
client = ollama.Client(timeout=300)


def save_log(log):
    """Add one interaction to the log file as a line of JSON."""
    with open("interaction_log.jsonl", "a") as file:
        file.write(json.dumps(log) + "\n")


def ask(question):
    """Send a question to the model, run any approved tool calls, and return the final answer."""
    messages = [{"role": "user", "content": question}]
    log = {"question": question, "tool_calls": [], "final_answer": None}
    for round_number in range(3):
        try:
            response = client.chat(model=MODEL, messages=messages, tools=tools, think=True)
        except httpx.TimeoutException:
            log["final_answer"] = "Timed out: the model took too long to answer."
            save_log(log)
            return log["final_answer"]
        messages.append(response.message)
        if not response.message.tool_calls:
            log["final_answer"] = response.message.content
            save_log(log)
            return response.message.content
        for call in response.message.tool_calls:
            name = call.function.name
            arguments = dict(call.function.arguments)
            result = run_tool(name, arguments)
            log["tool_calls"].append({"tool": name, "arguments": arguments,
                                      "result": result})
            messages.append({"role": "tool", "tool_name": name,
                             "content": json.dumps(result)})
    log["final_answer"] = "Stopped: the model asked for too many tool calls."
    save_log(log)
    return log["final_answer"]


questions = [
    "Look up the price of coffee.",              # lookup_product
    "How much do 3 bags of rice cost?",          # order_total
    "Convert 5 pounds to kilograms.",            # convert_units
    "What day comes after Monday?",              # no tool needed
    "How much do 500 bags of rice cost?",        # invalid argument
]
for question in questions:
    print("Question:", question)
    print("Answer:", ask(question))
    print()

bad_requests = [
    ("delete_inventory", {}),                                  # invalid tool name
    ("order_total", {"name": "rice", "quantity": "three"}),    # invalid argument
]
for name, arguments in bad_requests:
    result = run_tool(name, arguments)
    save_log({"question": "Scripted tool request (not from the model)",
              "tool_calls": [{"tool": name, "arguments": arguments, "result": result}],
              "final_answer": None})
    print("Scripted request:", name, arguments)
    print("Result:", result)
    print()   
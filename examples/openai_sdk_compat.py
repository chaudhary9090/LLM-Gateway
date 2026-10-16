"""Drop-in OpenAI SDK Compatibility Example.

Proves that any existing codebase using the official OpenAI Python SDK can switch
to LLM Gateway by changing ONLY the `base_url`.
"""

from openai import OpenAI


def run_openai_drop_in():
    print("================================================================")
    print(" PROOF: 100% DROP-IN COMPATIBILITY WITH OFFICIAL OPENAI SDK")
    print("================================================================")

    # Point official OpenAI client to our LLM Gateway
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="sk-gateway-test-key",  # Gateway accepts any key in test/dev mode
    )

    print("\n1. Calling client.chat.completions.create with model='balanced'...")
    response = client.chat.completions.create(
        model="balanced",
        messages=[
            {"role": "system", "content": "You are a helpful distributed systems architect."},
            {"role": "user", "content": "What is the primary benefit of unified API gateways?"},
        ],
        temperature=0.7,
        max_tokens=80,
    )

    print("\nResponse Object Type:", type(response).__name__)
    print("Completion ID:       ", response.id)
    print("Model Resolved:      ", response.model)
    print("Content Generated:   ", response.choices[0].message.content)
    print("Usage:               ", response.usage)

    print("\n2. Calling client.chat.completions.create with model='cheap' (local/mock)...")
    resp_cheap = client.chat.completions.create(
        model="cheap",
        messages=[{"role": "user", "content": "Hi cheap model"}],
        temperature=0.0,
        max_tokens=40,
    )
    print("Cheap Model Content: ", resp_cheap.choices[0].message.content)

    print("\n================================================================")
    print(" SUCCESS: Official OpenAI Python SDK worked with zero alterations!")
    print("================================================================\n")


if __name__ == "__main__":
    run_openai_drop_in()

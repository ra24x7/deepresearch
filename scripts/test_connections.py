"""Verify cloud credentials work before any pipeline code exists.

Run: uv run python scripts/test_connections.py

Checks, with one cheap real call each:
  1. OpenAI  — generation + no-retrieval baseline model (gpt-4o-mini)
  2. Bedrock — discovers which Claude models this key can see in the
               configured region, then invokes the best judge candidate
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

PROMPT = "Reply with exactly: OK"


def check_env_vars() -> bool:
    missing = [
        name
        for name in ("AWS_BEARER_TOKEN_BEDROCK", "AWS_REGION")
        if not os.environ.get(name)
    ]
    for name in missing:
        print(f"FAIL  missing env var: {name}")
    return not missing


def check_openai() -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        print("skip  OpenAI: no key set — generation runs on Bedrock Haiku for now (ADR 0001)")
        return True

    from openai import OpenAI

    try:
        response = OpenAI().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=5,
        )
        print(f"OK    OpenAI gpt-4o-mini responded: {response.choices[0].message.content!r}")
        return True
    except Exception as exc:
        print(f"FAIL  OpenAI: {exc}")
        return False


def discover_claude_models(region: str) -> list[str]:
    import boto3

    bedrock = boto3.client("bedrock", region_name=region)
    found: list[str] = []
    try:
        profiles = bedrock.list_inference_profiles()["inferenceProfileSummaries"]
        found += [p["inferenceProfileId"] for p in profiles if "claude" in p["inferenceProfileId"].lower()]
    except Exception as exc:
        print(f"note  cannot list inference profiles: {exc}")
    try:
        models = bedrock.list_foundation_models(byProvider="Anthropic")["modelSummaries"]
        found += [m["modelId"] for m in models]
    except Exception as exc:
        print(f"note  cannot list foundation models: {exc}")
    return list(dict.fromkeys(found))


def judge_candidates(models: list[str]) -> list[str]:
    sonnets = [m for m in models if "sonnet" in m.lower()]
    # Prefer newest sonnets; cross-region inference profiles (apac./us. prefix)
    # before bare model ids, since new models often require a profile
    sonnets.sort(key=lambda m: ("sonnet-4-6" not in m, "." not in m.split(".")[0], m), reverse=False)
    return sonnets


def check_bedrock(region: str) -> bool:
    import boto3

    models = discover_claude_models(region)
    if not models:
        print(f"FAIL  Bedrock: no Claude models visible in {region} — wrong region, or key lacks list permissions")
        return False
    print(f"      Claude models visible in {region}:")
    for model in models:
        print(f"        {model}")

    runtime = boto3.client("bedrock-runtime", region_name=region)

    def invoke_first(candidates: list[str], role: str) -> bool:
        for model_id in candidates:
            try:
                response = runtime.converse(
                    modelId=model_id,
                    messages=[{"role": "user", "content": [{"text": PROMPT}]}],
                    inferenceConfig={"maxTokens": 5},
                )
                text = response["output"]["message"]["content"][0]["text"]
                print(f"OK    Bedrock {model_id} responded: {text!r}")
                print(f"      --> {role} model id for config: {model_id}")
                return True
            except Exception as exc:
                print(f"note  {model_id}: {exc}")
        print(f"FAIL  Bedrock: no invocable {role} model — check Model access in the console")
        return False

    haikus = sorted(
        (m for m in models if "haiku-4" in m.lower()),
        key=lambda m: "." not in m.split(".")[0],
    )
    return invoke_first(judge_candidates(models), "judge") & invoke_first(haikus, "generation")


def main() -> int:
    load_dotenv()
    if not check_env_vars():
        return 1
    openai_ok = check_openai()
    bedrock_ok = check_bedrock(os.environ["AWS_REGION"])
    print()
    print("All connections OK" if openai_ok and bedrock_ok else "Some connections FAILED")
    return 0 if openai_ok and bedrock_ok else 1


if __name__ == "__main__":
    sys.exit(main())

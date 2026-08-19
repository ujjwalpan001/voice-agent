import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

from backend.agent.prompts import SYSTEM_PROMPT
from backend.config import settings

async def run_text_test():
    """Runs a pure text simulation by talking directly to Groq, bypassing Pipecat's audio frame system entirely."""
    
    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

    prompt = SYSTEM_PROMPT.replace("{restaurant_name}", settings.RESTAURANT_NAME).replace("{customer_phone}", "TEXT_TEST")
    messages = [{"role": "system", "content": prompt}]
    
    print("\n" + "="*50)
    print("🚀 TERMINAL CHAT SIMULATION STARTED")
    print("==================================================")
    print("(Type your message and press Enter. Type 'quit' to exit.)\n")

    while True:
        # Get user input
        user_msg = input("\033[94m👤 You:\033[0m ")
        if user_msg.lower() in ["quit", "exit"]:
            break
            
        if not user_msg.strip():
            continue
            
        messages.append({"role": "user", "content": user_msg})
        
        # Talk to LLM
        print("\033[92m🤖 AI:\033[0m ", end="", flush=True)
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            stream=True
        )
        
        full_reply = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                full_reply += text
        
        print("\n")
        messages.append({"role": "assistant", "content": full_reply})

if __name__ == "__main__":
    asyncio.run(run_text_test())

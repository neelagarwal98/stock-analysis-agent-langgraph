# =============================================================================
# Human-in-the-Loop (HITL) Stock Trading Agent with LangGraph
# -----------------------------------------------------------------------------
# This script demonstrates how to add human approval (HITL) during execution.
# Steps:
# 1. Ask for stock price.
# 2. Request to buy stocks; execution pauses for human approval.
# 3. Resume execution based on user input ("yes" or "no").
# =============================================================================

from langchain.chat_models import init_chat_model
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from dotenv import load_dotenv
load_dotenv()

class State(TypedDict):
    """
    Conversation state schema:
    - messages: list of {"role", "content"} chat messages maintained per thread
    """
    messages: Annotated[list, add_messages]

@tool
def get_stock_price(symbol: str) -> float:
    '''Return the current price of a stock given the stock symbol'''
    # Mocked for demo purposes
    return {"MSFT" : 200.3, "AAPL" : 100.4, "AMZN" : 150.0, "RIL" : 87.6}.get(symbol, 0.0)

@tool
def buy_stocks(symbol: str, quantity: int, total_price: float) -> str:
    '''Buy stocks given the stock symbol and quantity'''
    # Pause execution and request human confirmation
    decision = interrupt(f"Approve buying {quantity} {symbol} stocks for ${total_price:.2f}?")

    # Resume execution based on the user's decision
    if decision == "yes":
        return f"You bought {quantity} shares of {symbol} for a total price of {total_price}"
    else:
        return "Buying declined."

tools = [get_stock_price, buy_stocks]

llm = init_chat_model("google_genai:gemini-2.0-flash")
llm_with_tools = llm.bind_tools(tools)

def chatbot_node(state: State):
    """
    Node that invokes the LLM with tools and returns the response.
    """
    msg = llm_with_tools.invoke(state["messages"])
    return {"messages": [msg]}

memory = MemorySaver() # Maintain per-thread state

builder = StateGraph(State)
builder.add_node("chatbot", chatbot_node)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", tools_condition)
builder.add_edge("tools", "chatbot")
# Note: END is implied after the last chatbot call

graph = builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "buy_thread"}}

# Step 1: user asks price
state = graph.invoke({"messages": [{"role": "user", "content": "What is the current price of 10 MSFT stocks?"}]}, config=config)
print(state["messages"][-1].content)

# Step 2: user asks to buy
state = graph.invoke({"messages": [{"role": "user", "content": "Buy 10 MSFT stocks at current price."}]}, config=config)
print(state.get("__interrupt__"))

# Step 3: User provides input ("yes" or "no"), then execution resumes
decision = input("Approve (yes/no): ")
state = graph.invoke(Command(resume=decision), config=config)
print(state["messages"][-1].content)
"""
api.py FastAPI接口层
对外HTTP入口，专供Apifox测试
请求地址：POST http://127.0.0.1:8000/api/agent04/run
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field
from main import run_agent_workflow

app = FastAPI(title="多Agent软件开发团队接口", version="1.0.0")


# 请求体模型
class AgentRunRequest(BaseModel):
    user_input: str = Field(description="用户原始输入，闲聊或者软件开发需求", min_length=1)
    thread_id: str | None = Field(default=None, description="会话ID；传入则复用历史上下文，不传自动生成")


# 响应模型
class AgentRunResponse(BaseModel):
    code: int
    msg: str
    data: dict


@app.post("/api/agent04/run", response_model=AgentRunResponse)
async def agent_run(req: AgentRunRequest):
    """
    多Agent工作流执行接口
    - 普通闲聊：直接返回原生LLM回复，流程结束
    - 软件开发需求：驱动完整多Agent团队执行，thread_id维持会话记忆，支持迭代修改需求
    """
    state_obj, used_thread_id = run_agent_workflow(
        user_input=req.user_input,
        thread_id=req.thread_id
    )

    resp_data = {
        "thread_id": used_thread_id,
        "is_finished": state_obj.is_finished,
        "final_output": state_obj.final_output,
        "step_log": state_obj.step_log,
        "refined_requirement": state_obj.refined_requirement
    }

    return {
        "code": 0,
        "msg": "ok",
        "data": resp_data
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)

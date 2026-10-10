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
    resume: str | None = Field(default=None, description="架构评审确认/意见；首次调用不传，架构中断后携带thread_id+resume继续")


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
    - 软件开发需求：驱动完整多Agent团队执行
    - 架构评审中断：流程在架构师后暂停，返回架构方案等待用户确认（code=100）
      → 用户带 thread_id + resume 再次调用继续（确认或提意见）
    """
    result = run_agent_workflow(
        user_input=req.user_input,
        thread_id=req.thread_id,
        resume_value=req.resume
    )

    # 架构评审中断：返回待确认状态，等用户确认/提意见
    if result.get("pending"):
        return {
            "code": 100,
            "msg": "pending_architecture_review",
            "data": {
                "thread_id": result["thread_id"],
                "pending": True,
                "message": result["message"],
                "architecture_doc": result["architecture_doc"],
                "tech_stack": result["tech_stack"],
                "project_brief": result["project_brief"],
                "hint": "架构师已完成架构，请确认。回复'继续'进入开发，或提出优化意见交回架构师调整。再次调用请带 thread_id + resume 字段。"
            }
        }

    state_obj = result["state"]
    resp_data = {
        "thread_id": result["thread_id"],
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

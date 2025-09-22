from opentelemetry.trace import Span
import json


def set_span_attribute(span: Span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


class CrewAISpanAttributes:
    def __init__(self, span: Span, instance) -> None:
        self.span = span
        self.instance = instance
        self.crew = {"tasks": [], "agents": [], "llms": []}
        self.process_instance()

    def process_instance(self):
        instance_type = self.instance.__class__.__name__
        method_mapping = {
            "Crew": self._process_crew,
            "Agent": self._process_agent,
            "Task": self._process_task,
            "LLM": self._process_llm,
        }
        method = method_mapping.get(instance_type)
        if method:
            method()

    def _process_crew(self):
        self._populate_crew_attributes()
        for key, value in self.crew.items():
            self._set_attribute(f"crewai.crew.{key}", value)

    def _process_agent(self):
        agent_data = self._populate_agent_attributes()
        for key, value in agent_data.items():
            self._set_attribute(f"crewai.agent.{key}", value)

    def _process_task(self):
        task_data = self._populate_task_attributes()
        for key, value in task_data.items():
            self._set_attribute(f"crewai.task.{key}", value)

    def _process_llm(self):
        llm_data = self._populate_llm_attributes()
        for key, value in llm_data.items():
            self._set_attribute(f"crewai.llm.{key}", value)

    def _populate_crew_attributes(self):
        for key, value in self.instance.__dict__.items():
            if value is None:
                continue
            if key == "tasks":
                self._parse_tasks(value)
            elif key == "agents":
                self._parse_agents(value)
            elif key == "llms":
                self._parse_llms(value)
            else:
                self.crew[key] = str(value)

    def _populate_agent_attributes(self):
        return self._extract_attributes(self.instance)

    def _populate_task_attributes(self):
        task_data = self._extract_attributes(self.instance)
        if "agent" in task_data:
            task_data["agent"] = self.instance.agent.role if self.instance.agent else None
        return task_data

    def _populate_llm_attributes(self):
        return self._extract_attributes(self.instance)

    def _parse_agents(self, agents):
        self.crew["agents"] = [
            self._extract_agent_data(agent) for agent in agents if agent is not None
        ]

    def _parse_tasks(self, tasks):
        self.crew["tasks"] = [
            {
                "agent": task.agent.role if task.agent else None,
                "description": task.description,
                "async_execution": task.async_execution,
                "expected_output": task.expected_output,
                "human_input": task.human_input,
                "tools": task.tools,
                "output_file": task.output_file,
            }
            for task in tasks
        ]

    def _parse_llms(self, llms):
        self.crew["tasks"] = [
            {
                "temperature": llm.temperature,
                "max_tokens": llm.max_tokens,
                "max_completion_tokens": llm.max_completion_tokens,
                "top_p": llm.top_p,
                "n": llm.n,
                "seed": llm.seed,
                "base_url": llm.base_url,
                "api_version": llm.api_version, }
            for llm in llms
        ]

    def _extract_agent_data(self, agent):
        model = (
            getattr(agent.llm, "model", None)
            or getattr(agent.llm, "model_name", None)
            or ""
        )

        return {
            "id": str(agent.id),
            "role": agent.role,
            "goal": agent.goal,
            "backstory": agent.backstory,
            "cache": agent.cache,
            "config": agent.config,
            "verbose": agent.verbose,
            "allow_delegation": agent.allow_delegation,
            "tools": agent.tools,
            "max_iter": agent.max_iter,
            "llm": str(model), }

    def _extract_attributes(self, obj):
        attributes = {}
        for key, value in obj.__dict__.items():
            if value is None:
                continue
            if key == "tools":
                attributes[key] = self._serialize_tools(value)
            else:
                attributes[key] = str(value)
        return attributes

    def _serialize_tools(self, tools):
        return json.dumps(
            [
                {k: v for k, v in vars(tool).items() if v is not None and k in ["name", "description"]}
                for tool in tools
            ]
        )

    def _set_attribute(self, key, value):
        if value:
            set_span_attribute(self.span, key, str(value) if isinstance(value, list) else value)

# Copyright (c) Alibaba, Inc. and its affiliates.

from dashscope.client.base_api import (CreateMixin, DeleteMixin, GetMixin,
                                       ListMixin, PutMixin, StreamEventMixin)
from dashscope.customize.customize_types import (Deployment, DeploymentDelete,
                                                 DeploymentList)


class Deployments(CreateMixin, DeleteMixin, ListMixin, GetMixin,
                  StreamEventMixin, PutMixin):
    SUB_PATH = 'deployments'
    """Deploy a model.
    """
    @classmethod
    def call(cls,
             model: str,
             capacity: int,
             version: str = None,
             suffix: str = None,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> Deployment:
        """Call to deployment a model service.

        Args:
            model (str): The model name.
            version (str, optional): The model version, unnecessary
                for fine-tuned model. Defaults to None.
            suffix (str, optional): The name suffix of the model deployment,
                If specified, the final model name will be model_suffix.
                Defaults to None.
            capacity (int, optional): The model service capacity.
            api_key (str, optional): The api-key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            Deployment: _description_
        """
        req = {'model_name': model, 'capacity': capacity}

        if version is not None:
            req['model_version'] = version
        if suffix is not None:
            req['suffix'] = suffix
        response = super().call(req,
                                api_key=api_key,
                                workspace=workspace,
                                **kwargs)
        return Deployment(**response)

    @classmethod
    def list(cls,
             page_no=1,
             page_size=10,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DeploymentList:
        """List deployments.

        Args:
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.
            page_no (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Items per page. Defaults to 10.
            workspace (str): The dashscope workspace id.

        Returns:
            Deployment: The deployment list.
        """
        response = super().list(page_no=page_no,
                                page_size=page_size,
                                api_key=api_key,
                                workspace=workspace,
                                **kwargs)
        return DeploymentList(**response)

    @classmethod
    def get(cls,
            deployed_model: str,
            api_key: str = None,
            workspace: str = None,
            **kwargs) -> Deployment:
        """Get model deployment information.

        Args:
            deployed_model (str): The deployment_id.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            Deployment: The deployment information.
        """
        response = super().get(deployed_model,
                               api_key=api_key,
                               workspace=workspace,
                               **kwargs)
        return Deployment(**response)

    @classmethod
    def delete(cls,
               deployed_model: str,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> DeploymentDelete:
        """Delete model deployment.

        Args:
            deployed_model (str): The deployment id.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            Deployment: The delete result.
        """
        response = super().delete(deployed_model,
                                  api_key=api_key,
                                  workspace=workspace,
                                  **kwargs)
        return DeploymentDelete(**response)

    @classmethod
    def scale(cls,
              deployed_model: str,
              capacity: int,
              api_key: str = None,
              workspace: str = None,
              **kwargs) -> Deployment:
        """Scaling model deployment.

        Args:
            deployment_id (str): The deployment id.
            capacity (int): The target service capacity.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            Deployment: The delete result.
        """
        req = {'deployed_model': deployed_model, 'capacity': capacity}
        path = '%s/%s/scale' % (cls.SUB_PATH.lower(), deployed_model)
        response = super().put(deployed_model,
                               req,
                               path=path,
                               api_key=api_key,
                               workspace=workspace,
                               **kwargs)
        return Deployment(**response)

#!/usr/bin/env python
import argparse
import sys
import time
import os
from http import HTTPStatus

import dashscope
from dashscope.aigc import Generation
from dashscope.common.constants import (DeploymentStatus, FilePurpose,
                                        TaskStatus)
from dashscope.utils.oss_utils import OssUtils


def print_failed_message(rsp):
    print('Failed, request_id: %s, status_code: %s, code: %s, message: %s' %
          (rsp.request_id, rsp.status_code, rsp.code, rsp.message))


def text_generation(args):
    response = Generation.call(args.model, args.prompt, stream=args.stream)
    if args.stream:
        for rsp in response:
            if rsp.status_code == HTTPStatus.OK:
                print(rsp.output)
                print(rsp.usage)
            else:
                print_failed_message(rsp)
    else:
        if response.status_code == HTTPStatus.OK:
            print(response.output)
            print(response.usage)
        else:
            print_failed_message(response)


class FineTunes:
    @classmethod
    def call(cls, args):
        params = {}
        if args.n_epochs is not None:
            params['n_epochs'] = args.n_epochs
        if args.batch_size is not None:
            params['batch_size'] = args.batch_size
        if args.learning_rate is not None:
            params['learning_rate'] = args.learning_rate
        if args.prompt_loss is not None:
            params['prompt_loss'] = args.prompt_loss
        if args.params:
            params.update(args.params)

        rsp = dashscope.FineTunes.call(
            model=args.model,
            training_file_ids=args.training_file_ids,
            validation_file_ids=args.validation_file_ids,
            mode=args.mode,
            hyper_parameters=params)
        if rsp.status_code == HTTPStatus.OK:
            print('Create fine-tune job success, job_id: %s' %
                  rsp.output['job_id'])
            cls.wait(rsp.output['job_id'])
        else:
            print_failed_message(rsp)

    @classmethod
    def wait(cls, job_id):
        try:
            while True:
                rsp = dashscope.FineTunes.get(job_id)
                if rsp.status_code == HTTPStatus.OK:
                    if rsp.output['status'] == TaskStatus.FAILED:
                        print('Fine-tune FAILED!')
                        break
                    elif rsp.output['status'] == TaskStatus.CANCELED:
                        print('Fine-tune task CANCELED')
                        break
                    elif rsp.output['status'] == TaskStatus.RUNNING:
                        print(
                            'Fine-tuning is RUNNING, start get output stream.')
                        cls.stream_events(job_id)
                    elif rsp.output['status'] == TaskStatus.SUCCEEDED:
                        print('Fine-tune task success, fine-tuned model:%s' %
                              rsp.output['finetuned_output'])
                        break
                    else:
                        print('The fine-tune task is: %s' %
                              rsp.output['status'])
                        time.sleep(30)
                else:
                    print_failed_message(rsp)
        except Exception:
            print(
                'You can stream output via: dashscope fine_tunes.stream -j %s'
                % job_id)

    @classmethod
    def get(cls, args):
        rsp = dashscope.FineTunes.get(args.job)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output['status'] == TaskStatus.FAILED:
                print('Fine-tune failed!')
            elif rsp.output['status'] == TaskStatus.CANCELED:
                print('Fine-tune task canceled')
            elif rsp.output['status'] == TaskStatus.SUCCEEDED:
                print('Fine-tune task success, fine-tuned model : %s' %
                      rsp.output['finetuned_output'])
            else:
                print('The fine-tune task is: %s' % rsp.output['status'])
        else:
            print_failed_message(rsp)

    @classmethod
    def list(cls, args):
        rsp = dashscope.FineTunes.list(page=args.start_page,
                                       page_size=args.page_size)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output is not None:
                for job in rsp.output['jobs']:
                    if job['status'] == TaskStatus.SUCCEEDED:
                        print(
                            'job: %s, status: %s, base model: %s, fine-tuned model: %s'  # noqa E501
                            %  # noqa
                            (job['job_id'], job['status'], job['model'],
                             job['finetuned_output']))
                    else:
                        print('job: %s, status: %s, base model: %s' %
                              (job['job_id'], job['status'], job['model']))
            else:
                print('There is no fine-tuned model.')
        else:
            print_failed_message(rsp)

    @classmethod
    def stream_events(cls, job_id):
        # check job status if job is completed, get log.
        rsp = dashscope.FineTunes.get(job_id)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output['status'] in [
                    TaskStatus.FAILED, TaskStatus.CANCELED,
                    TaskStatus.SUCCEEDED
            ]:
                print('Fine-tune job: %s is %s' %
                      (job_id, rsp.output['status']))
                cls.log(job_id)
                return
        else:
            print_failed_message(rsp)
            return
        # start streaming events.
        try:
            stream_events = dashscope.FineTunes.stream_events(job_id)
            for rsp in stream_events:
                if rsp.status_code == HTTPStatus.OK:
                    print(rsp.output)
                else:
                    print_failed_message(rsp)
        except Exception:
            print(
                'You can stream output via: dashscope fine-tunes.stream -j %s'
                % job_id)

    @classmethod
    def events(cls, args):
        cls.stream_events(args.job)

    @classmethod
    def log(cls, job_id):
        start = 1
        n_line = 1000  # 1000 line per request
        while True:
            rsp = dashscope.FineTunes.logs(job_id, offset=start, line=n_line)
            if rsp.status_code == HTTPStatus.OK:
                for line in rsp.output['logs']:
                    print(line)
                if rsp.output['total'] < n_line:
                    break
                else:
                    start += n_line
            else:
                print_failed_message(rsp)

    @classmethod
    def cancel(cls, args):
        rsp = dashscope.FineTunes.cancel(args.job)
        if rsp.status_code == HTTPStatus.OK:
            print('Cancel fine-tune job: %s success!')
        else:
            print_failed_message(rsp)

    @classmethod
    def delete(cls, args):
        rsp = dashscope.FineTunes.delete(args.job)
        if rsp.status_code == HTTPStatus.OK:
            print('fine_tune job: %s delete success' % args.job)
        else:
            print_failed_message(rsp)

class Oss:
    @classmethod
    def upload(cls, args):
        print('Start oss.upload: model=%s, file=%s, api_key=%s' % (args.model, args.file, args.api_key))
        if not args.file or not args.model:
            print('Please specify the model and file path')
            return

        file_path = os.path.expanduser(args.file)
        if not os.path.exists(file_path):
            print('File %s does not exist' % file_path)
            return

        api_key = os.environ.get('DASHSCOPE_API_KEY', args.api_key)
        if not api_key:
            print('Please set your DashScope API key as environment variable '
                  'DASHSCOPE_API_KEY or pass it as argument by -k/--api_key')
            return

        oss_url = OssUtils.upload(model=args.model,
                                  file_path=file_path,
                                  api_key=api_key)

        if not oss_url:
            print('Failed to upload file: %s' % file_path)
            return

        print('Uploaded oss url: %s' % oss_url)

class Files:
    @classmethod
    def upload(cls, args):
        rsp = dashscope.Files.upload(file_path=args.file,
                                     purpose=args.purpose,
                                     description=args.description)
        print(rsp)
        if rsp.status_code == HTTPStatus.OK:
            print('Upload success, file id: %s' %
                  rsp.output['uploaded_files'][0]['file_id'])
        else:
            print_failed_message(rsp)

    @classmethod
    def get(cls, args):
        rsp = dashscope.Files.get(file_id=args.id)
        if rsp.status_code == HTTPStatus.OK:
            print('file_id: %s, name: %s, description: %s' %
                  (rsp.output['file_id'], rsp.output['name'],
                   rsp.output['description']))
        else:
            print_failed_message(rsp)

    @classmethod
    def list(cls, args):
        rsp = dashscope.Files.list(page=args.start_page,
                                   page_size=args.page_size)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output is not None:
                for f in rsp.output['files']:
                    print('file_id: %s, name: %s, description: %s, time: %s' %
                          (f['file_id'], f['name'], f['description'],
                           f['gmt_create']))
            else:
                print('There is no uploaded file.')
        else:
            print_failed_message(rsp)

    @classmethod
    def delete(cls, args):
        rsp = dashscope.Files.delete(args.id)
        if rsp.status_code == HTTPStatus.OK:
            print('Delete success')
        else:
            print_failed_message(rsp)


class Deployments:
    @classmethod
    def call(cls, args):
        rsp = dashscope.Deployments.call(model=args.model,
                                         capacity=args.capacity,
                                         suffix=args.suffix)
        if rsp.status_code == HTTPStatus.OK:
            deployed_model = rsp.output['deployed_model']
            print('Create model: %s deployment' % deployed_model)
            try:
                while True:  # wait for deployment ok.
                    status = dashscope.Deployments.get(deployed_model)
                    if status.status_code == HTTPStatus.OK:
                        if status.output['status'] in [
                                DeploymentStatus.PENDING,
                                DeploymentStatus.DEPLOYING
                        ]:
                            time.sleep(30)
                            print('Deployment %s is %s' %
                                  (deployed_model, status.output['status']))
                        else:
                            print('Deployment: %s status: %s' %
                                  (deployed_model, status.output['status']))
                            break

                    else:
                        print_failed_message(rsp)
            except Exception:
                print('You can get deployment status via: \
                        dashscope deployments.get -d %s' % deployed_model)
        else:
            print_failed_message(rsp)

    @classmethod
    def get(cls, args):
        rsp = dashscope.Deployments.get(args.deploy)
        if rsp.status_code == HTTPStatus.OK:
            print('Deployed model: %s capacity: %s status: %s' %
                  (rsp.output['deployed_model'], rsp.output['capacity'],
                   rsp.output['status']))
        else:
            print_failed_message(rsp)

    @classmethod
    def list(cls, args):
        rsp = dashscope.Deployments.list(page_no=args.start_page,
                                         page_size=args.page_size)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output is not None:
                if 'deployments' not in rsp.output or len(
                        rsp.output['deployments']) == 0:
                    print('There is no deployed model!')
                    return
                for deployment in rsp.output['deployments']:
                    print('Deployed_model: %s, model: %s, status: %s' %
                          (deployment['deployed_model'],
                           deployment['model_name'], deployment['status']))
            else:
                print('There is no deployed model.')
        else:
            print_failed_message(rsp)

    @classmethod
    def update(cls, args):
        rsp = dashscope.Deployments.update(args.deployed_model, args.version)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output is not None:
                if 'deployments' not in rsp.output:
                    print('There is no deployed model!')
                    return
                for deployment in rsp.output['deployments']:
                    print('Deployed_model: %s, model: %s, status: %s' %
                          (deployment['deployed_model'],
                           deployment['model_name'], deployment['status']))
            else:
                print('There is no deployed model.')
        else:
            print_failed_message(rsp)

    @classmethod
    def scale(cls, args):
        rsp = dashscope.Deployments.scale(args.deployed_model, args.capacity)
        if rsp.status_code == HTTPStatus.OK:
            if rsp.output is not None:
                print('Deployed_model: %s, model: %s, status: %s' %
                      (rsp.output['deployed_model'], rsp.output['model_name'],
                       rsp.output['status']))
            else:
                print('There is no deployed model.')
        else:
            print_failed_message(rsp)

    @classmethod
    def delete(cls, args):
        rsp = dashscope.Deployments.delete(args.deploy)
        if rsp.status_code == HTTPStatus.OK:
            print('Deployed model: %s delete success' % args.deploy)
        else:
            print_failed_message(rsp)


# from: https://gist.github.com/vadimkantorov/37518ff88808af840884355c845049ea
class ParseKVAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        for each in values:
            try:
                key, value = each.split('=')
                getattr(namespace, self.dest)[key] = value
            except ValueError as ex:
                message = '\nTraceback: {}'.format(ex)
                message += "\nError on '{}' || It should be 'key=value'".format(
                    each)
                raise argparse.ArgumentError(self, str(message))


def main():
    parser = argparse.ArgumentParser(
        prog='dashscope', description='dashscope command line tools.')
    parser.add_argument('-k', '--api-key', help='Dashscope API key.')
    sub_parsers = parser.add_subparsers(help='Api subcommands')
    text_generation_parser = sub_parsers.add_parser('generation.call')
    text_generation_parser.add_argument('-p',
                                        '--prompt',
                                        type=str,
                                        required=True,
                                        help='Input prompt')
    text_generation_parser.add_argument('-m',
                                        '--model',
                                        type=str,
                                        required=True,
                                        help='The model to call.')
    text_generation_parser.add_argument('--history',
                                        type=str,
                                        required=False,
                                        help='The history of the request.')
    text_generation_parser.add_argument('-s',
                                        '--stream',
                                        default=False,
                                        action='store_true',
                                        help='Use stream mode default false.')
    text_generation_parser.set_defaults(func=text_generation)
    fine_tune_call = sub_parsers.add_parser('fine_tunes.call')
    fine_tune_call.add_argument(
        '-t',
        '--training_file_ids',
        required=True,
        nargs='+',
        help='Training file ids which upload by File command.')
    fine_tune_call.add_argument(
        '-v',
        '--validation_file_ids',
        required=False,
        nargs='+',
        default=[],
        help='Validation file ids which upload by File command.')
    fine_tune_call.add_argument('-m',
                                '--model',
                                type=str,
                                required=True,
                                help='The based model to start fine-tune.')
    fine_tune_call.add_argument(
        '--mode',
        type=str,
        required=False,
        choices=['sft', 'efficient_sft'],
        help='Select fine-tune mode sft or efficient_sft')
    fine_tune_call.add_argument('-e',
                                '--n_epochs',
                                type=int,
                                required=False,
                                help='How many epochs to fine-tune.')
    fine_tune_call.add_argument('-b',
                                '--batch_size',
                                type=int,
                                required=False,
                                help='How big is batch_size.')
    fine_tune_call.add_argument('-l',
                                '--learning_rate',
                                type=float,
                                required=False,
                                help='The fine-tune learning rate.')
    fine_tune_call.add_argument('-p',
                                '--prompt_loss',
                                type=float,
                                required=False,
                                help='The fine-tune prompt loss.')
    fine_tune_call.add_argument(
        '--hyper_parameters',
        nargs='+',
        dest='params',
        action=ParseKVAction,
        help='Extra hyper parameters accepts by key1=value1 key2=value2',
        metavar='KEY1=VALUE1')
    fine_tune_call.set_defaults(func=FineTunes.call)
    fine_tune_get = sub_parsers.add_parser('fine_tunes.get')
    fine_tune_get.add_argument('-j',
                               '--job',
                               type=str,
                               required=True,
                               help='The fine-tune job id.')
    fine_tune_get.set_defaults(func=FineTunes.get)
    fine_tune_delete = sub_parsers.add_parser('fine_tunes.delete')
    fine_tune_delete.add_argument('-j',
                                  '--job',
                                  type=str,
                                  required=True,
                                  help='The fine-tune job id.')
    fine_tune_delete.set_defaults(func=FineTunes.delete)
    fine_tune_stream = sub_parsers.add_parser('fine_tunes.stream')
    fine_tune_stream.add_argument('-j',
                                  '--job',
                                  type=str,
                                  required=True,
                                  help='The fine-tune job id.')
    fine_tune_stream.set_defaults(func=FineTunes.events)
    fine_tune_list = sub_parsers.add_parser('fine_tunes.list')
    fine_tune_list.add_argument('-s',
                                '--start_page',
                                type=int,
                                default=1,
                                help='Start of page, default 1')
    fine_tune_list.add_argument('-p',
                                '--page_size',
                                type=int,
                                default=10,
                                help='The page size, default 10')
    fine_tune_list.set_defaults(func=FineTunes.list)
    fine_tune_cancel = sub_parsers.add_parser('fine_tunes.cancel')
    fine_tune_cancel.add_argument('-j',
                                  '--job',
                                  type=str,
                                  required=True,
                                  help='The fine-tune job id.')
    fine_tune_cancel.set_defaults(func=FineTunes.cancel)

    oss_upload = sub_parsers.add_parser('oss.upload')
    oss_upload.add_argument(
        '-f',
        '--file',
        type=str,
        required=True,
        help='The file path to upload',
    )
    oss_upload.add_argument(
        '-m',
        '--model',
        type=str,
        required=True,
        help='The model name',
    )
    oss_upload.add_argument(
        '-k',
        '--api_key',
        type=str,
        required=False,
        help='The dashscope api key',
    )
    oss_upload.set_defaults(func=Oss.upload)

    file_upload = sub_parsers.add_parser('files.upload')
    file_upload.add_argument(
        '-f',
        '--file',
        type=str,
        required=True,
        help='The file path to upload',
    )
    file_upload.add_argument(
        '-p',
        '--purpose',
        default=FilePurpose.fine_tune,
        const=FilePurpose.fine_tune,
        nargs='?',
        help='Purpose to upload file[fine-tune]',
        required=True,
    )
    file_upload.add_argument(
        '-d',
        '--description',
        type=str,
        help='The file description.',
        required=False,
    )
    file_upload.set_defaults(func=Files.upload)
    file_get = sub_parsers.add_parser('files.get')
    file_get.add_argument('-i',
                          '--id',
                          type=str,
                          required=True,
                          help='The file ID')
    file_get.set_defaults(func=Files.get)
    file_delete = sub_parsers.add_parser('files.delete')
    file_delete.add_argument('-i',
                             '--id',
                             type=str,
                             required=True,
                             help='The files ID')
    file_delete.set_defaults(func=Files.delete)
    file_list = sub_parsers.add_parser('files.list')
    file_list.add_argument('-s',
                           '--start_page',
                           type=int,
                           default=1,
                           help='Start of page, default 1')
    file_list.add_argument('-p',
                           '--page_size',
                           type=int,
                           default=10,
                           help='The page size, default 10')
    file_list.set_defaults(func=Files.list)

    deployments_call = sub_parsers.add_parser('deployments.call')
    deployments_call.add_argument('-m',
                                  '--model',
                                  required=True,
                                  help='The model ID')
    deployments_call.add_argument('-s',
                                  '--suffix',
                                  required=False,
                                  help=('The suffix of the deployment, \
            lower cased characters 8 chars max.'))
    deployments_call.add_argument('-c',
                                  '--capacity',
                                  type=int,
                                  required=False,
                                  default=1,
                                  help='The target capacity')
    deployments_call.set_defaults(func=Deployments.call)

    deployments_get = sub_parsers.add_parser('deployments.get')
    deployments_get.add_argument('-d',
                                 '--deploy',
                                 required=True,
                                 help='The deployed model.')
    deployments_get.set_defaults(func=Deployments.get)
    deployments_delete = sub_parsers.add_parser('deployments.delete')
    deployments_delete.add_argument('-d',
                                    '--deploy',
                                    required=True,
                                    help='The deployed model.')
    deployments_delete.set_defaults(func=Deployments.delete)
    deployments_list = sub_parsers.add_parser('deployments.list')
    deployments_list.add_argument('-s',
                                  '--start_page',
                                  type=int,
                                  default=1,
                                  help='Start of page, default 1')
    deployments_list.add_argument('-p',
                                  '--page_size',
                                  type=int,
                                  default=10,
                                  help='The page size, default 10')
    deployments_list.set_defaults(func=Deployments.list)
    deployments_scale = sub_parsers.add_parser('deployments.scale')
    deployments_scale.add_argument('-d',
                                   '--deployed_model',
                                   type=str,
                                   required=True,
                                   help='The deployed model to scale')
    deployments_scale.add_argument('-c',
                                   '--capacity',
                                   type=int,
                                   required=True,
                                   help='The target capacity')
    deployments_scale.set_defaults(func=Deployments.scale)

    args = parser.parse_args()
    if args.api_key is not None:
        dashscope.api_key = args.api_key
    args.func(args)


if __name__ == '__main__':
    sys.exit(main())

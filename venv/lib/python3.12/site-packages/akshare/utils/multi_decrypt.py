"""
利用多进行执行 js 代码方案

1. 未能解决 gevent 调用问题
2. 导致 js 代码执行缓慢
3. 该方案废弃，这里仅作参考

同时发现 gevent 里面无法调用异步的接口
"""

import concurrent.futures


# 定义在模块级别的函数
def js_executor_function(js_code_str, method, args):
    """在新进程中执行 JavaScript 代码的函数"""
    from py_mini_racer import MiniRacer

    js_code = MiniRacer()
    js_code.eval(js_code_str)

    if method == "call":
        fn_name = args[0]
        fn_args = args[1:]
        return js_code.call(fn_name, *fn_args)
    elif method == "eval":
        return js_code.eval(args[0])
    else:
        raise ValueError(f"不支持的方法: {method}")


def execute_js_in_executor(js_code_str, method, *args, timeout=30):
    """
    使用 ProcessPoolExecutor 在独立进程中执行 JavaScript

    参数:
        js_code_str: JavaScript 代码字符串
        method: 'call' 或 'eval'
        args: 如果 method 是 'call'，第一个参数是函数名，后续是函数参数
              如果 method 是 'eval'，只需提供一个参数：要评估的代码
        timeout: 超时时间（秒）

    返回:
        执行结果
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(js_executor_function, js_code_str, method, args)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            # 清理资源并抛出超时异常
            executor.shutdown(wait=False)
            raise TimeoutError("JavaScript 执行超时")

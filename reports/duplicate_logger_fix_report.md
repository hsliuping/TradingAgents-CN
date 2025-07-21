# 重复Logger定义修复报告

## 概要

- 扫描文件总数: 321
- 发现重复定义文件数: 98
- 成功修复文件数: 98
- 总共移除重复定义: 108
- 修复失败文件数: 0

## 修复详情

### fix_stock_code_issue.py

- 原有logger定义数: 3
  - 第12行: `logger = get_logger('default')`
  - 第106行: `logger = get_logger("default")`
  - 第139行: `logger = get_logger('default')`

### main.py

- 原有logger定义数: 2
  - 第6行: `logger = get_logger('default')`
  - 第8行: `logger = get_logger('default')`

### quick_syntax_check.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('default')`
  - 第18行: `logger = get_logger('default')`

### stock_code_validator.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('default')`
  - 第19行: `logger = get_logger('default')`

### syntax_checker.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('default')`
  - 第18行: `logger = get_logger('default')`

### test_fundamentals_tracking.py

- 原有logger定义数: 2
  - 第25行: `logger = get_logger("default")`
  - 第97行: `logger = get_logger("default")`

### test_simple_tracking.py

- 原有logger定义数: 3
  - 第25行: `logger = get_logger("default")`
  - 第75行: `logger = get_logger("default")`
  - 第125行: `logger = get_logger("default")`

### data\scripts\sync_stock_info_to_mongodb.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('scripts')`
  - 第397行: `logger = get_logger('scripts')`

### examples\batch_analysis.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('default')`
  - 第24行: `logger = get_logger('default')`

### examples\cli_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('cli')`
  - 第15行: `logger = get_logger('cli')`

### examples\config_management_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第253行: `logger = get_logger('default')`

### examples\custom_analysis_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第277行: `logger = get_logger('default')`

### examples\data_dir_config_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第243行: `logger = get_logger('default')`

### examples\demo_deepseek_analysis.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('default')`
  - 第208行: `logger = get_logger('default')`

### examples\my_stock_analysis.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第123行: `logger = get_logger('default')`

### examples\simple_analysis_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第202行: `logger = get_logger('default')`

### examples\stock_list_example.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('default')`
  - 第16行: `logger = get_logger('default')`

### examples\stock_query_examples.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第249行: `logger = get_logger('default')`

### examples\token_tracking_demo.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('default')`
  - 第33行: `logger = get_logger('default')`

### examples\tushare_demo.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第258行: `logger = get_logger('default')`

### examples\dashscope_examples\demo_dashscope.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第124行: `logger = get_logger('default')`

### examples\dashscope_examples\demo_dashscope_chinese.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第146行: `logger = get_logger('default')`

### examples\dashscope_examples\demo_dashscope_no_memory.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第115行: `logger = get_logger('default')`

### examples\dashscope_examples\demo_dashscope_simple.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第111行: `logger = get_logger('default')`

### examples\openai\demo_openai.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第22行: `logger = get_logger('default')`

### scripts\analyze_data_calls.py

- 原有logger定义数: 2
  - 第18行: `logger = get_logger('scripts')`
  - 第20行: `logger = get_logger('scripts')`

### scripts\build_docker_with_pdf.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第15行: `logger = get_logger('scripts')`

### scripts\install_pandoc.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('scripts')`
  - 第37行: `logger = get_logger('scripts')`

### scripts\install_pdf_tools.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('scripts')`
  - 第178行: `logger = get_logger('scripts')`

### scripts\log_analyzer.py

- 原有logger定义数: 2
  - 第18行: `logger = get_logger('scripts')`
  - 第20行: `logger = get_logger('scripts')`

### scripts\migrate_to_unified_logging.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('scripts')`
  - 第18行: `logger = get_logger('scripts')`

### scripts\setup-docker.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第121行: `logger = get_logger('scripts')`

### scripts\deployment\create_github_release.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第16行: `logger = get_logger('scripts')`

### scripts\deployment\release_v0.1.2.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第16行: `logger = get_logger('scripts')`

### scripts\deployment\release_v0.1.3.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第16行: `logger = get_logger('scripts')`

### scripts\development\adaptive_cache_manager.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('scripts')`
  - 第114行: `logger = get_logger('scripts')`

### scripts\development\download_finnhub_sample_data.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('scripts')`
  - 第232行: `logger = get_logger('scripts')`

### scripts\development\fix_streamlit_watcher.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('scripts')`
  - 第21行: `logger = get_logger('scripts')`

### scripts\development\organize_scripts.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第15行: `logger = get_logger('scripts')`

### scripts\development\prepare_upstream_contribution.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('scripts')`
  - 第19行: `logger = get_logger('scripts')`

### scripts\git\branch_manager.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第16行: `logger = get_logger('scripts')`

### scripts\git\check_branch_overlap.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第15行: `logger = get_logger('scripts')`

### scripts\maintenance\branch_manager.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第139行: `logger = get_logger('scripts')`

### scripts\maintenance\cleanup_cache.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第146行: `logger = get_logger('scripts')`

### scripts\maintenance\finalize_script_organization.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第338行: `logger = get_logger('scripts')`

### scripts\maintenance\organize_root_scripts.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第233行: `logger = get_logger('scripts')`

### scripts\maintenance\sync_upstream.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('scripts')`
  - 第254行: `logger = get_logger('scripts')`

### scripts\maintenance\version_manager.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('scripts')`
  - 第18行: `logger = get_logger('scripts')`

### scripts\setup\configure_pip_source.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第224行: `logger = get_logger('scripts')`

### scripts\setup\initialize_system.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第323行: `logger = get_logger('scripts')`

### scripts\setup\init_database.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第221行: `logger = get_logger('scripts')`

### scripts\setup\manual_pip_config.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第214行: `logger = get_logger('scripts')`

### scripts\setup\migrate_env_to_config.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第172行: `logger = get_logger('scripts')`

### scripts\setup\setup_databases.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('scripts')`
  - 第198行: `logger = get_logger('scripts')`

### scripts\validation\check_dependencies.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('scripts')`
  - 第135行: `logger = get_logger('scripts')`

### scripts\validation\check_system_status.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第251行: `logger = get_logger('scripts')`

### scripts\validation\smart_config.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('scripts')`
  - 第63行: `logger = get_logger('scripts')`

### scripts\validation\verify_gitignore.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('scripts')`
  - 第15行: `logger = get_logger('scripts')`

### tradingagents\agents\utils\agent_utils.py

- 原有logger定义数: 3
  - 第23行: `logger = get_logger('agents')`
  - 第24行: `logger = get_logger("agents.utils")`
  - 第1133行: `logger = get_logger('agents')`

### tradingagents\api\stock_api.py

- 原有logger定义数: 3
  - 第15行: `logger = get_logger('agents')`
  - 第24行: `logger = get_logger("default")`
  - 第29行: `logger = get_logger('agents')`

### tradingagents\config\config_manager.py

- 原有logger定义数: 3
  - 第20行: `logger = get_logger('agents')`
  - 第21行: `logger = get_logger("config")`
  - 第455行: `logger = get_logger('agents')`

### tradingagents\config\mongodb_storage.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('agents')`
  - 第269行: `logger = get_logger('agents')`

### tradingagents\dataflows\akshare_utils.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('agents')`
  - 第240行: `logger = get_logger('agents')`

### tradingagents\dataflows\cache_manager.py

- 原有logger定义数: 2
  - 第18行: `logger = get_logger('agents')`
  - 第97行: `logger = get_logger('agents')`

### tradingagents\dataflows\data_source_manager.py

- 原有logger定义数: 3
  - 第15行: `logger = get_logger('agents')`
  - 第444行: `logger = get_logger('agents')`
  - 第445行: `logger = get_logger("default")`

### tradingagents\dataflows\db_cache_manager.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('agents')`
  - 第200行: `logger = get_logger('agents')`

### tradingagents\dataflows\finnhub_utils.py

- 原有logger定义数: 2
  - 第6行: `logger = get_logger('agents')`
  - 第8行: `logger = get_logger('agents')`

### tradingagents\dataflows\googlenews_utils.py

- 原有logger定义数: 2
  - 第11行: `logger = get_logger('agents')`
  - 第13行: `logger = get_logger('agents')`

### tradingagents\dataflows\hk_stock_utils.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('agents')`
  - 第17行: `logger = get_logger('agents')`

### tradingagents\dataflows\interface.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('agents')`
  - 第1594行: `logger = get_logger('agents')`

### tradingagents\dataflows\optimized_china_data.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('agents')`
  - 第549行: `logger = get_logger('agents')`

### tradingagents\dataflows\optimized_us_data.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('agents')`
  - 第275行: `logger = get_logger('agents')`

### tradingagents\dataflows\realtime_news_utils.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('agents')`
  - 第19行: `logger = get_logger('agents')`

### tradingagents\dataflows\stock_api.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('agents')`
  - 第93行: `logger = get_logger('agents')`

### tradingagents\dataflows\stock_data_service.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('agents')`
  - 第272行: `logger = get_logger('agents')`

### tradingagents\dataflows\tdx_utils.py

- 原有logger定义数: 2
  - 第15行: `logger = get_logger('agents')`
  - 第852行: `logger = get_logger('agents')`

### tradingagents\dataflows\tushare_utils.py

- 原有logger定义数: 3
  - 第17行: `logger = get_logger('agents')`
  - 第22行: `logger = get_logger("default")`
  - 第62行: `logger = get_logger('agents')`

### tradingagents\dataflows\utils.py

- 原有logger定义数: 2
  - 第9行: `logger = get_logger('agents')`
  - 第11行: `logger = get_logger('agents')`

### tradingagents\dataflows\yfin_utils.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('agents')`
  - 第19行: `logger = get_logger('agents')`

### tradingagents\dataflows\__init__.py

- 原有logger定义数: 2
  - 第8行: `logger = get_logger('agents')`
  - 第29行: `logger = get_logger('agents')`

### tradingagents\graph\trading_graph.py

- 原有logger定义数: 3
  - 第25行: `logger = get_logger('agents')`
  - 第26行: `logger = get_logger("graph.trading_graph")`
  - 第111行: `logger = get_logger('agents')`

### tradingagents\llm_adapters\dashscope_adapter.py

- 原有logger定义数: 2
  - 第22行: `logger = get_logger('agents')`
  - 第24行: `logger = get_logger('agents')`

### tradingagents\llm_adapters\dashscope_openai_adapter.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('agents')`
  - 第228行: `logger = get_logger('agents')`

### tradingagents\utils\logging_init.py

- 原有logger定义数: 4
  - 第30行: `logger = get_logger('tradingagents.init')`
  - 第59行: `logger = get_logger(logger_name)`
  - 第92行: `logger = get_logger('tradingagents.startup')`
  - 第118行: `logger = get_logger('tradingagents.shutdown')`

### tradingagents\utils\logging_manager.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('agents')`
  - 第21行: `logger = get_logger('agents')`

### upstream_contribution\batch1_caching\tradingagents\dataflows\cache_manager.py

- 原有logger定义数: 2
  - 第18行: `logger = get_logger('agents')`
  - 第97行: `logger = get_logger('agents')`

### upstream_contribution\batch1_caching\tradingagents\dataflows\optimized_us_data.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('agents')`
  - 第240行: `logger = get_logger('agents')`

### upstream_contribution\batch2_error_handling\tradingagents\agents\analysts\fundamentals_analyst.py

- 原有logger定义数: 2
  - 第9行: `logger = get_logger('agents')`
  - 第258行: `logger = get_logger('agents')`

### upstream_contribution\batch2_error_handling\tradingagents\agents\analysts\market_analyst.py

- 原有logger定义数: 2
  - 第9行: `logger = get_logger('agents')`
  - 第212行: `logger = get_logger('agents')`

### upstream_contribution\batch2_error_handling\tradingagents\dataflows\db_cache_manager.py

- 原有logger定义数: 2
  - 第17行: `logger = get_logger('agents')`
  - 第200行: `logger = get_logger('agents')`

### upstream_contribution\batch3_data_sources\tradingagents\dataflows\optimized_us_data.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('agents')`
  - 第240行: `logger = get_logger('agents')`

### utils\check_version_consistency.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第15行: `logger = get_logger('default')`

### utils\cleanup_unnecessary_dirs.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第15行: `logger = get_logger('default')`

### utils\update_data_source_references.py

- 原有logger定义数: 2
  - 第13行: `logger = get_logger('default')`
  - 第15行: `logger = get_logger('default')`

### web\components\analysis_form.py

- 原有logger定义数: 2
  - 第10行: `logger = get_logger('web')`
  - 第12行: `logger = get_logger('web')`

### web\components\results_display.py

- 原有logger定义数: 2
  - 第16行: `logger = get_logger('web')`
  - 第219行: `logger = get_logger('web')`

### web\utils\docker_pdf_adapter.py

- 原有logger定义数: 2
  - 第14行: `logger = get_logger('web')`
  - 第90行: `logger = get_logger('web')`

### web\utils\report_exporter.py

- 原有logger定义数: 2
  - 第19行: `logger = get_logger('web')`
  - 第533行: `logger = get_logger('web')`


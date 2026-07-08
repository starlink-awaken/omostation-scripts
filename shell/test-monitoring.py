"""
简单的测试脚本，验证监控指标采集器功能
"""

import asyncio
import json
from datetime import datetime

# 测试Minerva指标采集器
async def test_minerva_metrics():
    """测试Minerva业务指标采集器"""
    print("=== 测试Minerva业务指标采集器 ===")
    
    try:
        from minerva.metrics import (
            get_all_metrics,
            get_metrics_collector,
            record_research_attempt,
            record_pipeline_execution,
        )
        
        # 验证采集器可导入并初始化
        get_metrics_collector()
        
        # 模拟一些研究尝试
        print("\n1. 模拟研究尝试:")
        record_research_attempt(
            success=True,
            query="测试查询1",
            level="L2"
        )
        print("  ✅ 记录成功的研究尝试")
        
        record_research_attempt(
            success=False,
            error="测试错误1",
            query="测试查询2",
            level="L1"
        )
        print("  ✅ 记录失败的研究尝试")
        
        # 模拟Pipeline执行
        print("\n2. 模拟Pipeline执行:")
        record_pipeline_execution(
            pipeline_name="test-pipeline",
            steps=[
                {"name": "search", "success": True, "duration": 1.5},
                {"name": "extract", "success": True, "duration": 2.0},
                {"name": "report", "success": False, "duration": 0.5}
            ],
            completed=False
        )
        print("  ✅ 记录Pipeline执行")
        
        # 获取所有指标
        print("\n3. 获取所有指标:")
        all_metrics = get_all_metrics()
        print(json.dumps(all_metrics, indent=2, default=str))
        
        return True
        
    except ImportError as e:
        print(f"❌ Minerva metrics module not found: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


# 测试Agora Pipeline指标采集器
async def test_agora_metrics():
    """测试Agora Pipeline指标采集器"""
    print("=== 测试Agora Pipeline指标采集器 ===")
    
    try:
        from agora.metrics import (
            get_all_pipeline_metrics,
            get_pipeline_collector,
            record_execution,
        )
        
        # 验证采集器可导入并初始化
        get_pipeline_collector()
        
        # 模拟一些Pipeline执行
        print("\n1. 模拟Pipeline执行:")
        record_execution(
            pipeline_name="test-pipeline-1",
            steps=[
                {"name": "step1", "success": True, "duration": 1.0},
                {"name": "step2", "success": True, "duration": 2.0}
            ],
            completed=True
        )
        print("  ✅ 记录成功的Pipeline执行")
        
        record_execution(
            pipeline_name="test-pipeline-2",
            steps=[
                {"name": "step1", "success": False, "duration": 0.5},
                {"name": "step2", "success": False, "duration": 0.3}
            ],
            completed=False
        )
        print("  ✅ 记录失败的Pipeline执行")
        
        # 获取所有指标
        print("\n2. 获取所有指标:")
        all_metrics = get_all_pipeline_metrics()
        print(json.dumps(all_metrics, indent=2, default=str))
        
        return True
        
    except ImportError as e:
        print(f"❌ Agora metrics module not found: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


# 测试增强健康检查
async def test_enhanced_health():
    """测试增强的健康检查"""
    print("=== 测试增强健康检查 ===")
    
    try:
        from agora.monitoring.enhanced_health_cli import health_check_full, format_health_result
        
        # 创建模拟的args
        class MockArgs:
            json = False
            
        # 执行健康检查
        result = await health_check_full(MockArgs())
        
        print("\n健康检查结果:")
        print(format_health_result(result, False))
        
        return True
        
    except ImportError as e:
        print(f"❌ Enhanced health module not found: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


# 主测试函数
async def main():
    """运行所有测试"""
    print("🧪 开始监控体系功能测试")
    print(f"测试时间: {datetime.now().isoformat()}")
    print("")
    
    results = {}
    
    # 测试Minerva指标采集器
    print("测试1/3: Minerva业务指标采集器")
    results["minerva"] = await test_minerva_metrics()
    print("")
    
    # 测试Agora Pipeline指标采集器
    print("测试2/3: Agora Pipeline指标采集器")
    results["agora"] = await test_agora_metrics()
    print("")
    
    # 测试增强健康检查
    print("测试3/3: 增强健康检查")
    results["health"] = await test_enhanced_health()
    print("")
    
    # 总结结果
    print("="*60)
    print("📊 测试结果总结:")
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("")
    if all_passed:
        print("🎉 所有测试通过！监控体系基础功能正常工作。")
    else:
        print("⚠️  部分测试失败，请检查错误信息。")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    asyncio.run(main())

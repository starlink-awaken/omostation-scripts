"""
快速验证监控功能
"""

import sys
import os
import json
from pathlib import Path

# 测试Minerva模块
def test_minerva_module():
    """测试Minerva指标模块"""
    print("=== 测试Minerva指标模块 ===")
    
    try:
        sys.path.insert(0, "/Users/xiamingxing/Workspace/minerva/src")
        from metrics import get_all_metrics
        
        metrics = get_all_metrics()
        print("✅ Minerva模块加载成功")
        print(f"   指标数据: {list(metrics.keys())}")
        
        # 验证数据结构
        if "research" in metrics:
            research_data = metrics["research"]
            print("   研究指标:")
            print(f"     总尝试次数: {research_data.get('total_attempts', 0)}")
            print(f"     成功次数: {research_data.get('successful_attempts', 0)}")
            print(f"     成功率: {research_data.get('success_rate', 0):.1f}%")
        
        return True
    except ImportError as e:
        print(f"❌ Minerva模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ Minerva模块测试失败: {e}")
        return False


# 测试Agora模块
def test_agora_module():
    """测试Agora指标模块"""
    print("\n=== 测试Agora指标模块 ===")
    
    try:
        sys.path.insert(0, "/Users/xiamingxing/Workspace/agora/src")
        from metrics import get_all_pipeline_metrics
        
        metrics = get_all_pipeline_metrics()
        print("✅ Agora模块加载成功")
        print(f"   指标数据: {list(metrics.keys())}")
        
        # 验证数据结构
        if "pipeline" in metrics:
            pipeline_data = metrics["pipeline"]
            print("   Pipeline指标:")
            print(f"     总执行次数: {pipeline_data.get('total_executions', 0)}")
            print(f"     成功次数: {pipeline_data.get('successful_executions', 0)}")
            print(f"     完成率: {pipeline_data.get('completion_rate', 0):.1f}%")
        
        return True
    except ImportError as e:
        print(f"❌ Agora模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ Agora模块测试失败: {e}")
        return False


# 测试增强健康检查模块
def test_health_module():
    """测试增强健康检查模块"""
    print("\n=== 测试增强健康检查模块 ===")
    
    try:
        sys.path.insert(0, "/Users/xiamingxing/Workspace/agora/src")
        from monitoring.enhanced_health_cli import format_health_result
        
        # 测试格式化函数
        test_result = {
            "timestamp": "2026-05-24T10:00:00",
            "overall_status": "healthy",
            "services": {
                "test-service": {
                    "status": "healthy",
                    "message": "Test service"
                }
            },
            "performance": {
                "cpu_percent": 50,
                "memory_percent": 60,
                "disk_percent": 40
            }
        }
        
        formatted = format_health_result(test_result, False)
        print("✅ 增强健康检查模块加载成功")
        print("   格式化功能正常")
        
        return True
    except ImportError as e:
        print(f"❌ 增强健康检查模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 增强健康检查模块测试失败: {e}")
        return False


def test_file_existence():
    """测试关键文件是否存在"""
    print("\n=== 测试文件存在性 ===")
    
    files_to_check = [
        "/Users/xiamingxing/Workspace/minerva/src/minerva/metrics/__init__.py",
        "/Users/xiamingxing/Workspace/minerva/src/minerva/metrics/collector.py",
        "/Users/xiamingxing/Workspace/agora/src/agora/metrics/__init__.py",
        "/Users/xiamingxing/Workspace/agora/src/agora/metrics/collector.py",
        "/Users/xiamingxing/Workspace/agora/src/agora/monitoring/enhanced-health-cli.py",
        "/Users/xiamingxing/Workspace/agora/src/agora/monitoring/enhanced-health.py"
    ]
    
    all_exist = True
    for filepath in files_to_check:
        if Path(filepath).exists():
            print(f"  ✅ {Path(filepath).name}")
        else:
            print(f"  ❌ {Path(filepath).name} 不存在")
            all_exist = False
    
    return all_exist


def main():
    """主测试函数"""
    print("🧪 监控体系功能验证")
    print(f"验证时间: 2026-05-24")
    print("="*60)
    print("")
    
    results = {
        "minerva_module": test_minerva_module(),
        "agora_module": test_agora_module(),
        "health_module": test_health_module(),
        "file_existence": test_file_existence()
    }
    
    print("\n" + "="*60)
    print("📊 验证结果:")
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("")
    
    if all_passed:
        print("🎉 所有验证通过！监控体系基础组件正常工作。")
        print("\n下一步:")
        print("   1. 集成到现有CLI中")
        print("  2. 配置定时监控任务")
        print("  3. 设置告警通知")
    else:
        print("⚠️  部分验证失败，请检查:")
        print("  - 代码文件是否存在")
        print("  - 导入路径是否正确")
        print("  - 依赖是否满足")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

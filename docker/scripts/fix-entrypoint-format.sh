#!/bin/bash
# 修复 entrypoint 脚本格式（转换 CRLF 为 LF）

# 在容器内执行此脚本来修复文件格式
sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh
chmod +x /usr/local/bin/docker-entrypoint.sh

# 验证文件格式
if [ -f /usr/local/bin/docker-entrypoint.sh ]; then
    echo "✅ 文件存在"
    FIRST_LINE=$(head -n 1 /usr/local/bin/docker-entrypoint.sh)
    if [ "$FIRST_LINE" = "#!/bin/bash" ]; then
        echo "✅ 文件格式正确"
    else
        echo "⚠️  文件格式可能有问题: $FIRST_LINE"
    fi
else
    echo "❌ 文件不存在"
fi

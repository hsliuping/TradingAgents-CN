<template>
  <div class="global-index-grid">
    <el-row :gutter="20" v-if="data">
      <el-col :span="6" v-for="(items, area) in data" :key="area">
        <el-card class="area-card">
          <template #header>
            <span class="area-title">{{ getAreaName(area) }}</span>
          </template>
          <div class="index-list">
            <div
              v-for="item in items"
              :key="item.code"
              class="index-item"
            >
              <div class="index-info">
                <el-text :type="item.zdf > 0 ? 'danger' : 'success'" class="index-name">
                  {{ item.name }}
                </el-text>
              </div>
              <div class="index-value">
                <el-text :type="item.zdf > 0 ? 'danger' : 'success'">
                  {{ item.zxj }}
                </el-text>
                <el-text :type="item.zdf > 0 ? 'danger' : 'success'" class="index-change">
                  {{ item.zdf }}%
                </el-text>
              </div>
              <el-tag
                :type="item.state === 'open' ? 'success' : 'info'"
                size="small"
                class="index-state"
              >
                {{ item.state === 'open' ? '开市' : '休市' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-else description="暂无数据" />
  </div>
</template>

<script setup lang="ts">
interface Props {
  data?: Record<string, any[]>
}

const props = defineProps<Props>()

const getAreaName = (code: string) => {
  const nameMap: Record<string, string> = {
    'america': '美洲',
    'europe': '欧洲',
    'asia': '亚洲',
    'common': '常用',
    'other': '其他'
  }
  return nameMap[code] || code
}
</script>

<style scoped lang="scss">
.global-index-grid {
  .area-card {
    margin-bottom: 20px;

    .area-title {
      font-weight: bold;
      font-size: 16px;
    }

    .index-list {
      .index-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 0;
        border-bottom: 1px solid var(--el-border-color-lighter);

        &:last-child {
          border-bottom: none;
        }

        .index-info {
          flex: 1;

          .index-name {
            font-weight: 500;
          }
        }

        .index-value {
          text-align: right;
          flex: 1;

          .index-change {
            margin-left: 8px;
            font-weight: bold;
          }
        }

        .index-state {
          flex-shrink: 0;
        }
      }
    }
  }
}
</style>

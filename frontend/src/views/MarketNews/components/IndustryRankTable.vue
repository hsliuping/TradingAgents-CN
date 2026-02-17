<template>
  <el-card>
    <el-table :data="data" stripe>
      <el-table-column prop="bd_name" label="行业名称" width="120">
        <template #default="{ row }">
          <el-tag type="info">{{ row.bd_name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="bd_zdf" label="行业涨幅" sortable width="100">
        <template #default="{ row }">
          <el-text :type="row.bd_zdf > 0 ? 'danger' : 'success'">{{ row.bd_zdf }}%</el-text>
        </template>
      </el-table-column>
      <el-table-column prop="bd_zdf5" label="行业5日涨幅" width="120">
        <template #default="{ row }">
          <el-text :type="row.bd_zdf5 > 0 ? 'danger' : 'success'">{{ row.bd_zdf5 }}%</el-text>
        </template>
      </el-table-column>
      <el-table-column prop="nzg_name" label="领涨股" width="150">
        <template #default="{ row }">
          <el-text :type="row.nzg_zdf > 0 ? 'danger' : 'success'">
            {{ row.nzg_name }} <el-text type="info" size="small">{{ row.nzg_code }}</el-text>
          </el-text>
        </template>
      </el-table-column>
      <el-table-column prop="nzg_zdf" label="涨幅" width="80">
        <template #default="{ row }">
          <el-text :type="row.nzg_zdf > 0 ? 'danger' : 'success'">{{ row.nzg_zdf }}%</el-text>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!data || data.length === 0" description="暂无数据" />
  </el-card>
</template>

<script setup lang="ts">
interface Props {
  data?: any[]
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'sort-change', sort: string): void
}>()
</script>

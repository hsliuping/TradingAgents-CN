/**
 * 高级课程文件加载器映射
 * 
 * 由于Vite动态导入不支持中文文件名，需要预先定义所有文件的导入路径
 */

// 基础篇
import lesson1 from '../../../../docs/courses/advanced/expanded/01-基础篇-第1课.md?raw'
import lesson2 from '../../../../docs/courses/advanced/expanded/01-基础篇-第2课.md?raw'

// 选股篇
import lesson3 from '../../../../docs/courses/advanced/expanded/02-选股篇-第3课.md?raw'
import lesson4 from '../../../../docs/courses/advanced/expanded/02-选股篇-第4课.md?raw'
import lesson5 from '../../../../docs/courses/advanced/expanded/02-选股篇-第5课.md?raw'

// 择时篇
import lesson6 from '../../../../docs/courses/advanced/expanded/03-择时篇-第6课.md?raw'
import lesson7 from '../../../../docs/courses/advanced/expanded/03-择时篇-第7课.md?raw'
import lesson8 from '../../../../docs/courses/advanced/expanded/03-择时篇-第8课.md?raw'

// 执行篇
import lesson9 from '../../../../docs/courses/advanced/expanded/04-执行篇-第9课.md?raw'
import lesson10 from '../../../../docs/courses/advanced/expanded/04-执行篇-第10课.md?raw'

// 持仓管理篇
import lesson11 from '../../../../docs/courses/advanced/expanded/05-持仓管理篇-第11课.md?raw'
import lesson12 from '../../../../docs/courses/advanced/expanded/05-持仓管理篇-第12课.md?raw'

// 风险管理篇
import lesson13 from '../../../../docs/courses/advanced/expanded/06-风险管理篇-第13课.md?raw'
import lesson14 from '../../../../docs/courses/advanced/expanded/06-风险管理篇-第14课.md?raw'

// 复盘改进篇
import lesson15 from '../../../../docs/courses/advanced/expanded/07-复盘改进篇-第15课.md?raw'
import lesson16 from '../../../../docs/courses/advanced/expanded/07-复盘改进篇-第16课.md?raw'

// 短线实战篇
import lesson17 from '../../../../docs/courses/advanced/expanded/08-短线实战篇-第17课.md?raw'
import lesson18 from '../../../../docs/courses/advanced/expanded/08-短线实战篇-第18课.md?raw'
import lesson19 from '../../../../docs/courses/advanced/expanded/08-短线实战篇-第19课.md?raw'

// 中长线实战篇
import lesson20 from '../../../../docs/courses/advanced/expanded/09-中长线实战篇-第20课.md?raw'
import lesson21 from '../../../../docs/courses/advanced/expanded/09-中长线实战篇-第21课.md?raw'
import lesson22 from '../../../../docs/courses/advanced/expanded/09-中长线实战篇-第22课.md?raw'

// 交易计划建立
import lesson23 from '../../../../docs/courses/advanced/expanded/10-交易计划建立-第23课.md?raw'
import lesson24 from '../../../../docs/courses/advanced/expanded/10-交易计划建立-第24课.md?raw'

/**
 * 课程文件映射表
 * key: 文件名（如 "01-基础篇-第1课.md"）
 * value: 导入的Markdown内容
 */
export const courseFileMap: Record<string, string> = {
  '01-基础篇-第1课.md': lesson1,
  '01-基础篇-第2课.md': lesson2,
  '02-选股篇-第3课.md': lesson3,
  '02-选股篇-第4课.md': lesson4,
  '02-选股篇-第5课.md': lesson5,
  '03-择时篇-第6课.md': lesson6,
  '03-择时篇-第7课.md': lesson7,
  '03-择时篇-第8课.md': lesson8,
  '04-执行篇-第9课.md': lesson9,
  '04-执行篇-第10课.md': lesson10,
  '05-持仓管理篇-第11课.md': lesson11,
  '05-持仓管理篇-第12课.md': lesson12,
  '06-风险管理篇-第13课.md': lesson13,
  '06-风险管理篇-第14课.md': lesson14,
  '07-复盘改进篇-第15课.md': lesson15,
  '07-复盘改进篇-第16课.md': lesson16,
  '08-短线实战篇-第17课.md': lesson17,
  '08-短线实战篇-第18课.md': lesson18,
  '08-短线实战篇-第19课.md': lesson19,
  '09-中长线实战篇-第20课.md': lesson20,
  '09-中长线实战篇-第21课.md': lesson21,
  '09-中长线实战篇-第22课.md': lesson22,
  '10-交易计划建立-第23课.md': lesson23,
  '10-交易计划建立-第24课.md': lesson24,
}

/**
 * 根据文件名获取课程内容
 */
export function getCourseContent(fileName: string): string | null {
  return courseFileMap[fileName] || null
}


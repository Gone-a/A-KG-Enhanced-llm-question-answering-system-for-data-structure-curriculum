<template>
  <div class="graph-container">
    <div class="graph-header">
      <h2 class="graph-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="graph-icon">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="currentColor"/>
        </svg>
        知识图谱可视化
      </h2>
      <div class="graph-controls">
        <button class="control-btn" @click="relayout" title="重新布局">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" fill="currentColor"/>
          </svg>
        </button>
        <button class="control-btn" @click="toggleFullscreen" title="全屏显示">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" fill="currentColor"/>
          </svg>
        </button>
        <button class="control-btn" @click="exportImage" title="导出图片">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/>
          </svg>
        </button>
      </div>
    </div>
    <div ref="graphContainer" class="graph-view"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, onUnmounted, defineProps } from 'vue';
import * as d3 from 'd3';

// 接收父组件传入的图形数据
const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({ nodes: [], links: [] }),
    description: '包含nodes和links的JSON数据'
  }
});

// 组件内部状态
const graphContainer = ref(null);
const graphStatus = ref("初始化中...");
let simulation = null;
let layoutTimer = null;
let dataCopy = null; // 添加全局dataCopy变量

// 清除当前图形
const clearGraph = () => {
  if (graphContainer.value) {
    d3.select(graphContainer.value).selectAll("*").remove();
  }
  if (simulation) {
    simulation.stop();
    simulation = null;
  }
  // 清理定时器
  if (layoutTimer) {
    clearInterval(layoutTimer);
    layoutTimer = null;
  }
  
  // 清理节点位置缓存，确保下次重绘时完全随机
  if (dataCopy && dataCopy.nodes) {
    dataCopy.nodes.forEach(node => {
      delete node.x;
      delete node.y;
      delete node.vx;
      delete node.vy;
      delete node.fx;
      delete node.fy;
      delete node.index;
    });
  }
};

// 绘制图形 - 确保此函数被正确调用
const drawGraph = (data) => {
  // 深拷贝数据，避免修改原始响应式数据
  dataCopy = JSON.parse(JSON.stringify(data)); 
  // 清空现有图形
  clearGraph();
  
  // 验证容器是否存在
  if (!graphContainer.value) {
    graphStatus.value = "错误: 图形容器不存在";
    console.error("图形容器元素未找到");
    return;
  }
  
  // 验证数据格式
  if (!data || !data.nodes || !data.links) {
    graphStatus.value = "错误: 无效的数据格式";
    console.error("无效的数据格式，必须包含nodes和links属性");
    return;
  }
  
  // 验证数据内容
  if (data.nodes.length === 0) {
    graphStatus.value = "警告: 没有节点数据";
    return;
  }
  
  graphStatus.value = "正在绘制图形...";
  
  // 获取容器尺寸并确保有明确的大小
  const container = graphContainer.value;
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 600;

  console.log(width);
  console.log(height);
  
  // 创建SVG元素
  const svg = d3.select(container)
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");
  
  // 创建渐变和滤镜定义
  const defs = svg.append("defs");
  
  // 创建链接渐变
  const linkGradient = defs.append("linearGradient")
    .attr("id", "linkGradient")
    .attr("gradientUnits", "userSpaceOnUse");
  
  linkGradient.append("stop")
    .attr("offset", "0%")
    .attr("stop-color", "#6366f1")
    .attr("stop-opacity", 0.8);
    
  linkGradient.append("stop")
    .attr("offset", "100%")
    .attr("stop-color", "#8b5cf6")
    .attr("stop-opacity", 0.6);

  // 创建节点发光效果滤镜
  const glowFilter = defs.append("filter")
    .attr("id", "glow")
    .attr("x", "-50%")
    .attr("y", "-50%")
    .attr("width", "200%")
    .attr("height", "200%");
    
  glowFilter.append("feGaussianBlur")
    .attr("stdDeviation", "3")
    .attr("result", "coloredBlur");
    
  const feMerge = glowFilter.append("feMerge");
  feMerge.append("feMergeNode").attr("in", "coloredBlur");
  feMerge.append("feMergeNode").attr("in", "SourceGraphic");

  // 创建箭头标记
  defs.selectAll("marker")
    .data(["end"])
    .enter().append("marker")
    .attr("id", d => d)
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 20)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#6366f1")
    .attr("opacity", 0.8);
  
  // 颜色调色板
  const colorPalette = [
    "#6366f1", "#8b5cf6", "#06b6d4", "#10b981", 
    "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6"
  ];

  // 字符串哈希函数
  function stringToHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  // 创建力导向图模拟
  simulation = d3.forceSimulation(dataCopy.nodes)
    .force("link", d3.forceLink(dataCopy.links).id(d => d.id).distance(() => 80 + Math.random() * 40)) // 减少链接距离随机性
    .force("charge", d3.forceManyBody().strength(() => -300 - Math.random() * 100)) // 减少排斥力随机性
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(35))
    // 添加温和的随机扰动力
    .force("random", () => {
      dataCopy.nodes.forEach(node => {
        // 添加轻微的随机扰动，保持自然感
        node.vx += (Math.random() - 0.5) * 0.2;
        node.vy += (Math.random() - 0.5) * 0.2;
      });
    });
  
  // 为每个节点设置随机初始位置，避免固定模式
  dataCopy.nodes.forEach((node) => {
    // 使用适度随机的初始位置
    const randomAngle = Math.random() * 2 * Math.PI;
    const randomRadius = Math.random() * Math.min(width, height) * 0.25 + 50;
    
    // 适度的随机偏移
    const centerX = width / 2 + (Math.random() - 0.5) * width * 0.2;
    const centerY = height / 2 + (Math.random() - 0.5) * height * 0.2;
    
    node.x = centerX + Math.cos(randomAngle) * randomRadius;
    node.y = centerY + Math.sin(randomAngle) * randomRadius;
    
    // 确保节点在视图范围内
    node.x = Math.max(30, Math.min(width - 30, node.x));
    node.y = Math.max(30, Math.min(height - 30, node.y));
    
    // 添加温和的随机初始速度
    node.vx = (Math.random() - 0.5) * 2;
    node.vy = (Math.random() - 0.5) * 2;
  });
  
  // 添加防重叠机制
  const avoidOverlap = () => {
    for (let i = 0; i < dataCopy.nodes.length; i++) {
      for (let j = i + 1; j < dataCopy.nodes.length; j++) {
        const nodeA = dataCopy.nodes[i];
        const nodeB = dataCopy.nodes[j];
        
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const minDistance = 80; // 最小距离
        
        if (distance < minDistance && distance > 0) {
          const pushForce = (minDistance - distance) / distance * 0.5;
          const pushX = dx * pushForce;
          const pushY = dy * pushForce;
          
          nodeA.x -= pushX;
          nodeA.y -= pushY;
          nodeB.x += pushX;
          nodeB.y += pushY;
        }
      }
    }
  };
  
  // 执行防重叠
  avoidOverlap();

  // 创建链接
  const link = svg.append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(dataCopy.links)
    .enter().append("line")
    .attr("stroke", "url(#linkGradient)")
    .attr("stroke-width", 2.5)
    .attr("stroke-opacity", 0.8)
    .attr("marker-end", "url(#end)")
    .style("filter", "drop-shadow(0 2px 4px rgba(99, 102, 241, 0.2))")
    .attr("class", "link-line")
    .style("stroke-linecap", "round");

  const linkLabels = svg.append("g")
    .attr("class", "link-labels")
    .selectAll("text")
    .data(dataCopy.links)
    .enter().append("text")
    .text(d => d.relation)
    .attr("font-size", 11)
    .attr("fill", "#475569")
    .attr("text-anchor", "middle")
    .attr("pointer-events", "none")
    .attr("font-weight", "600")
    .attr("font-family", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif")
    .style("text-shadow", "0 1px 3px rgba(255,255,255,0.9)")
    .style("opacity", 0.9)
    .attr("dy", "-5px");
  
  // 创建节点组
  const node = svg.append("g")
    .attr("class", "nodes")
    .selectAll(".node")
    .data(dataCopy.nodes)
    .enter().append("g")
    .attr("class", "node")
    .style("cursor", "grab")
    .call(d3.drag()
      .on("start", dragStarted)
      .on("drag", dragged)
      .on("end", dragEnded));
  
  // 增强的节点设计
  node.append("circle")
    .attr("r", 26)
    .attr("fill", d => {
      const hash = stringToHash(d.id);
      const colorIndex = Math.abs(hash) % colorPalette.length;
      return colorPalette[colorIndex];
    })
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 3)
    .style("filter", "drop-shadow(0 4px 12px rgba(0,0,0,0.15))")
    .attr("class", "node-circle")
    .style("opacity", 0.95)
    .style("transition", "all 0.3s ease");
  
  // 节点文本标签
  node.append("text")
    .attr("dy", ".35em")
    .attr("text-anchor", "middle")
    .text(d => {
      if (d.name.length <= 4) return d.name;
      if (d.name.length <= 6) return d.name;
      return d.name.substring(0, 4) + '...';
    })
    .attr("font-size", "11px")
    .attr("fill", "#ffffff")
    .attr("font-weight", "700")
    .attr("pointer-events", "none")
    .attr("font-family", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif")
    .style("text-shadow", "0 1px 3px rgba(0,0,0,0.4)")
    .attr("class", "node-text");

  // 添加节点悬停效果
  node
    .on("mouseenter", function(event, d) {
      // 高亮当前节点
      d3.select(this).select(".node-circle")
        .transition()
        .duration(200)
        .attr("r", 30)
        .style("filter", "url(#glow) drop-shadow(0 6px 16px rgba(99, 102, 241, 0.4))");
      
      d3.select(this).select(".node-text")
        .transition()
        .duration(200)
        .attr("font-size", "13px")
        .style("font-weight", "700");
        
      // 高亮相关链接和标签
      link.style("stroke-opacity", l => 
        (l.source === d || l.target === d) ? 1 : 0.2
      ).style("stroke-width", l => 
        (l.source === d || l.target === d) ? 3.5 : 2.5
      );
      
      linkLabels.style("opacity", l => 
        (l.source === d || l.target === d) ? 1 : 0.2
      ).style("font-weight", l => 
        (l.source === d || l.target === d) ? "700" : "600"
      );
      
      // 高亮相关节点
      node.selectAll(".node-circle").style("opacity", n => 
        n === d || dataCopy.links.some(l => 
          (l.source === d && l.target === n) || (l.target === d && l.source === n)
        ) ? 1 : 0.3
      );
      
      node.selectAll(".node-text").style("opacity", n => 
        n === d || dataCopy.links.some(l => 
          (l.source === d && l.target === n) || (l.target === d && l.source === n)
        ) ? 1 : 0.3
      );
    })
    .on("mouseleave", function() {
      // 恢复所有节点
      node.selectAll(".node-circle")
        .transition()
        .duration(200)
        .attr("r", 26)
        .style("filter", "url(#glow)")
        .style("opacity", 1);
      
      node.selectAll(".node-text")
        .transition()
        .duration(200)
        .attr("font-size", "11px")
        .style("font-weight", "600")
        .style("opacity", 1);
        
      // 恢复所有链接
      link.style("stroke-opacity", 0.8)
          .style("stroke-width", 2.5);
      
      linkLabels.style("opacity", 0.9)
                .style("font-weight", "600");
    });



  // 更新力导向图布局
  simulation.on("tick", () => {
    // 限制节点在视图范围内
    dataCopy.nodes.forEach(d => {
      d.x = Math.max(30, Math.min(width - 30, d.x));
      d.y = Math.max(30, Math.min(height - 30, d.y));
    });
    
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);
    
    linkLabels.each(function(d) {
      const midX = (d.source.x + d.target.x) / 2; // 边的中点X
      const midY = (d.source.y + d.target.y) / 2; // 边的中点Y
      d3.select(this)
        .attr("x", midX)
        .attr("y", midY);
    });
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });
  
  // 添加温和的定期重新布局功能
  let layoutTimer = null;
  const startPeriodicLayout = () => {
    // 清除之前的定时器
    if (layoutTimer) {
      clearInterval(layoutTimer);
    }
    
    // 每15秒进行一次温和的布局调整
    layoutTimer = setInterval(() => {
      if (simulation) {
        // 为所有节点添加轻微的随机扰动
        dataCopy.nodes.forEach(node => {
          // 添加温和的随机扰动
          node.vx += (Math.random() - 0.5) * 1.0;
          node.vy += (Math.random() - 0.5) * 1.0;
        });
        
        // 温和地重新启动模拟
        simulation.alpha(0.3).alphaTarget(0.1).restart();
        
        // 2秒后降低alpha目标值
        setTimeout(() => {
          if (simulation) {
            simulation.alphaTarget(0);
          }
        }, 2000);
      }
    }, 15000); // 延长到15秒间隔
  };
  
  // 模拟完成后更新状态并启动定期布局
  simulation.on("end", () => {
    graphStatus.value = `图形绘制完成 (节点: ${dataCopy.nodes.length}, 边: ${dataCopy.links.length})`;
    startPeriodicLayout();
  });
  
  // 拖拽事件处理函数
  function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }
  
  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }
  
  function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
  
  console.log("图形绘制函数已执行", data);
  graphStatus.value = "图形绘制中...";
};

// 当组件挂载时初始化 - 确保在此处调用drawGraph
onMounted(() => {
  graphStatus.value = "组件已挂载，准备绘制图形";
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize);
  
  // 确保DOM更新后再绘制图形
  nextTick(() => {
    console.log("首次绘制图形");
    const currentData = props.graphData;
    drawGraph(currentData);
  });
});

// 当组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  clearGraph();
  // 确保清理所有定时器
  if (layoutTimer) {
    clearInterval(layoutTimer);
    layoutTimer = null;
  }
});

// 处理窗口大小变化
const handleResize = () => {
  graphStatus.value = "窗口大小变化，重绘图形";
  const currentData = props.graphData;
  drawGraph(currentData);
};

// 监听数据变化，更新图形 - 确保数据变化时调用drawGraph
watch([() => props.graphData], () => {
  nextTick(() => {
    console.log("数据变化，重绘图形");
    
    // 在重绘前强制清理所有缓存数据，确保完全随机
    if (dataCopy && dataCopy.nodes) {
      dataCopy.nodes.forEach(node => {
        delete node.x;
        delete node.y;
        delete node.vx;
        delete node.vy;
        delete node.fx;
        delete node.fy;
        delete node.index;
      });
    }
    
    // 添加随机延迟，进一步打破任何可能的模式
    const randomDelay = Math.random() * 100;
    setTimeout(() => {
      const currentData = props.graphData;
      drawGraph(currentData);
    }, randomDelay);
  });
},{ flush: 'post' });
</script>

<style scoped>
/* 图形容器样式 - 现代化设计 */
.graph-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px;
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -1px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}

.graph-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.graph-icon {
  color: #6366f1;
  font-size: 18px;
}

.graph-controls {
  display: flex;
  gap: 8px;
}

.control-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  font-size: 14px;
}

.control-btn:hover {
  background: #6366f1;
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.graph-view {
  flex: 1;
  border-radius: 12px;
  background: radial-gradient(circle at 30% 20%, rgba(99, 102, 241, 0.05) 0%, transparent 50%),
              radial-gradient(circle at 70% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 50%),
              linear-gradient(135deg, rgba(255, 255, 255, 0.8) 0%, rgba(248, 250, 252, 0.9) 100%);
  position: relative;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.06);
}

/* 控制按钮样式 */
.controls {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  gap: 12px;
  z-index: 10;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.btn-primary {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2);
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(99, 102, 241, 0.3);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.8);
  color: #64748b;
  border: 1px solid rgba(203, 213, 225, 0.5);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.95);
  color: #475569;
  transform: translateY(-1px);
}

/* 状态信息样式 */
.status-info {
  position: absolute;
  bottom: 20px;
  left: 20px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* SVG 样式增强 */
.graph-view svg {
  border-radius: 12px;
}

/* 节点和链接的全局样式 */
.nodes .node {
  cursor: grab;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nodes .node:active {
  cursor: grabbing;
}

.links line {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.link-labels text {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .graph-container {
    padding: 15px;
    border-radius: 12px;
  }
  
  .controls {
    top: 15px;
    right: 15px;
    padding: 8px 12px;
    gap: 8px;
  }
  
  .btn {
    padding: 6px 12px;
    font-size: 11px;
  }
  
  .status-info {
    font-size: 11px;
    padding: 6px 10px;
  }
}

/* 精致的动画效果 */
@keyframes nodeAppear {
  from {
    opacity: 0;
    transform: scale(0.3) rotate(-180deg);
  }
  to {
    opacity: 0.95;
    transform: scale(1) rotate(0deg);
  }
}

@keyframes linkAppear {
  from {
    opacity: 0;
    stroke-dasharray: 5, 5;
    stroke-dashoffset: 10;
  }
  to {
    opacity: 0.7;
    stroke-dasharray: none;
    stroke-dashoffset: 0;
  }
}

@keyframes labelFadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 0.8;
    transform: translateY(0);
  }
}

.nodes .node {
  animation: nodeAppear 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

.links line {
  animation: linkAppear 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.link-labels text {
  animation: labelFadeIn 1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  animation-delay: 0.3s;
  opacity: 0;
}
/* 连线动画效果 */
.link-line {
  stroke-dasharray: 5, 5;
  animation: linkFlow 2s linear infinite;
  transition: all 0.3s ease;
}

.link-line:hover {
  stroke-width: 3.5 !important;
  stroke-opacity: 1 !important;
  filter: drop-shadow(0 3px 6px rgba(99, 102, 241, 0.4)) !important;
}

@keyframes linkFlow {
  0% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: 10;
  }
}

/* 连线标签动画 */
.link-labels text {
  transition: all 0.3s ease;
}

.link-labels text:hover {
  font-size: 12px !important;
  fill: #6366f1 !important;
  font-weight: 700 !important;
}
</style>

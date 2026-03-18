import json
import os
import re
from pathlib import Path

def generate_mirror_radial_tree(scraped_data_dir, output_file):
    mirrors_json_path = os.path.join(scraped_data_dir, "mirrors.json")
    
    if not os.path.exists(mirrors_json_path):
        print(f"Error: {mirrors_json_path} not found.")
        return

    with open(mirrors_json_path, 'r', encoding='utf-8') as f:
        mirrors_data = json.load(f)

    # Transform mirrors data into a tree structure for ECharts
    # Root -> Group -> Sites
    tree_data = {
        "name": "Onion Mirror Network",
        "value": "root",
        "children": []
    }

    for group in mirrors_data.get("groups", []):
        group_node = {
            "name": group.get("common_title", "Unknown Group"),
            "value": group.get("id"),
            "children": []
        }
        
        for site in group.get("sites", []):
            # Check for screenshot
            image_path = f"{site}/images/index.png"
            full_image_path = os.path.join(scraped_data_dir, image_path)
            
            # If index.png doesn't exist, try to find any png in the images folder
            actual_image = ""
            if os.path.exists(full_image_path):
                actual_image = image_path
            else:
                img_dir = os.path.join(scraped_data_dir, site, "images")
                if os.path.exists(img_dir):
                    pngs = [f for f in os.listdir(img_dir) if f.endswith('.png')]
                    if pngs:
                        actual_image = f"{site}/images/{pngs[0]}"

            site_node = {
                "name": site[:10] + "..." + site[-5:], # Shorten for label
                "full_name": site,
                "value": site,
                "image": actual_image
            }
            group_node["children"].append(site_node)
        
        tree_data["children"].append(group_node)

    html_template = f"""
<!DOCTYPE html>
<html style="height: 100%">
<head>
    <meta charset="utf-8">
    <title>Mirror Network - Collapsible Radial Tree</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{ 
            margin: 0; 
            padding: 0; 
            background-color: #0b0e14; 
            color: #e6edf3;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            overflow: hidden;
        }}
        #main {{ width: 100vw; height: 100vh; }}
        .header {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 100;
            background: rgba(13, 17, 23, 0.85);
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #30363d;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }}
        h1 {{ margin: 0; font-size: 20px; color: #58a6ff; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }}
        p {{ margin: 10px 0 0; font-size: 13px; color: #8b949e; }}
        #tooltip-container {{
            position: fixed;
            display: none;
            padding: 15px;
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid #58a6ff;
            border-radius: 8px;
            pointer-events: none;
            z-index: 1000;
            box-shadow: 0 4px 20px rgba(0,0,0,0.6);
            max-width: 300px;
        }}
        #tooltip-container img {{
            width: 100%;
            border-radius: 4px;
            margin-bottom: 10px;
            border: 1px solid #30363d;
        }}
        .tooltip-title {{ color: #58a6ff; font-weight: bold; margin-bottom: 5px; font-size: 14px; word-break: break-all; }}
        .tooltip-meta {{ color: #8b949e; font-size: 11px; }}
    </style>
</head>
<body style="height: 100%; margin: 0">
    <div class="header">
        <h1>Mirror Network</h1>
        <p>Interactive Collapsible Radial Tree</p>
        <p style="font-size: 11px; margin-top: 5px;">Click nodes to expand/collapse. Hover for preview.</p>
    </div>
    <div id="main"></div>
    <div id="tooltip-container"></div>

    <script type="text/javascript">
        var chartDom = document.getElementById('main');
        var myChart = echarts.init(chartDom, 'dark');
        var option;

        const data = {json.dumps(tree_data)};

        myChart.showLoading();
        myChart.hideLoading();

        option = {{
            backgroundColor: '#0b0e14',
            tooltip: {{
                trigger: 'item',
                triggerOn: 'mousemove',
                formatter: function(params) {{
                    return ""; // We use custom tooltip
                }}
            }},
            series: [
                {{
                    type: 'tree',
                    data: [data],
                    top: '10%',
                    left: '10%',
                    bottom: '10%',
                    right: '10%',
                    layout: 'radial',
                    symbol: 'emptyCircle',
                    symbolSize: 10,
                    initialTreeDepth: 1,
                    animationDurationUpdate: 750,
                    emphasis: {{
                        focus: 'descendant'
                    }},
                    itemStyle: {{
                        color: '#58a6ff',
                        borderColor: '#58a6ff',
                        borderWidth: 2
                    }},
                    lineStyle: {{
                        color: '#30363d',
                        width: 1.5,
                        curveness: 0.5
                    }},
                    label: {{
                        position: 'relative',
                        rotate: 0,
                        verticalAlign: 'middle',
                        align: 'right',
                        fontSize: 12,
                        color: '#c9d1d9',
                        distance: 10
                    }},
                    leaves: {{
                        label: {{
                            position: 'relative',
                            rotate: 0,
                            verticalAlign: 'middle',
                            align: 'left'
                        }},
                        itemStyle: {{
                            color: '#3fb1e3',
                            borderColor: '#3fb1e3'
                        }}
                    }},
                    expandAndCollapse: true,
                    animationDuration: 550,
                    animationEasing: 'cubicOut'
                }}
            ]
        }};

        myChart.setOption(option);

        // Custom Tooltip Logic
        const tooltip = document.getElementById('tooltip-container');
        myChart.on('mouseover', 'series', function (params) {{
            if (params.data.image || params.data.full_name) {{
                let content = "";
                if (params.data.image) {{
                    content += `<img src="${{params.data.image}}" onerror="this.style.display='none'">`;
                }}
                content += `<div class="tooltip-title">${{params.data.full_name || params.name}}</div>`;
                if (params.data.value) {{
                    content += `<div class="tooltip-meta">ID: ${{params.data.value}}</div>`;
                }}
                
                tooltip.innerHTML = content;
                tooltip.style.display = 'block';
            }}
        }});

        myChart.on('mousemove', function (params) {{
            tooltip.style.left = (params.event.event.clientX + 20) + 'px';
            tooltip.style.top = (params.event.event.clientY + 20) + 'px';
        }});

        myChart.on('mouseout', function (params) {{
            tooltip.style.display = 'none';
        }});

        window.addEventListener('resize', function() {{
            myChart.resize();
        }});
    </script>
</body>
</html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    print(f"Radial tree visualization generated at {output_file}")

if __name__ == "__main__":
    generate_mirror_radial_tree("../scraped_data", "../scraped_data/mirror_radial_tree.html")

"""
AI Priority Agent - Core Engine
Powered by Claude AI --- analyzes tasks with RICE framework
"""

import os
import json
from typing import Optional, Dict, List, Any, Union
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Claude client
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables. Please check your .env file.")

client = Anthropic(api_key=api_key)

SYSTEM_PROMPT = """You are an AI Priority Agent that analyzes tasks using the RICE framework.

For each task, you MUST return a JSON object with:
- priority_score (1-10000): Overall priority based on RICE
- rice_breakdown: Object with reach (1-10), impact (1-10), confidence (1-10), effort (1-10)
- ai_acceleration_factor (1-10): How much AI speeds up this task
- estimated_hours_traditional: Hours without AI
- estimated_hours_ai: Hours with AI assistance
- recommended_order (1-N): Order to tackle tasks
- blocking_dependencies: List of task IDs this depends on
- cursor_specific_tips: Specific advice for using Cursor AI

Return ONLY valid JSON, no other text."""

def format_rice_score(rice_breakdown: Dict[str, int]) -> int:
    """
    Calculate RICE score from breakdown.
    RICE Score = (Reach * Impact * Confidence) / Effort, normalized to 1-10000
    
    Args:
        rice_breakdown: Dictionary with reach, impact, confidence, effort keys (values 1-10)
        
    Returns:
        RICE score normalized to 1-10000
    """
    # Get values with defaults
    reach = rice_breakdown.get("reach", 5)
    impact = rice_breakdown.get("impact", 5)
    confidence = rice_breakdown.get("confidence", 5)
    effort = rice_breakdown.get("effort", 5)
    
    # Ensure values are within range
    reach = max(1, min(10, reach))
    impact = max(1, min(10, impact))
    confidence = max(1, min(10, confidence))
    effort = max(1, min(10, effort))
    
    # Calculate raw RICE score: (Reach * Impact * Confidence) / Effort
    # Maximum raw score: (10 * 10 * 10) / 1 = 1000
    raw_score = (reach * impact * confidence) / effort
    
    # Normalize to 1-10000 scale
    # 1000 raw max * 10 = 10000
    normalized_score = int(raw_score * 10)
    
    # Ensure within bounds
    return max(1, min(10000, normalized_score))

def analyze_priorities(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Use Claude to analyze and score tasks using RICE framework.
    
    Args:
        tasks: List of task dictionaries with id, name, description, category
        
    Returns:
        Dictionary with analyzed tasks and metadata
    """
    if not tasks:
        return {"analyzed_tasks": [], "error": "No tasks provided"}
    
    try:
        response = client.messages.create(
            model="claude-3-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,  # Lower temperature for consistent scoring
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Analyze these tasks using RICE framework and return JSON:\n{json.dumps(tasks, indent=2)}"
            }]
        )
        
        content = response.content[0].text
        
        # Extract JSON from response (handle cases where Claude adds extra text)
        try:
            # Find the first { and last }
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                result = json.loads(json_str)
            else:
                # Try parsing the whole content
                result = json.loads(content)
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw response
            return {
                "analyzed_tasks": [],
                "raw_response": content,
                "error": "Failed to parse JSON from Claude response"
            }
        
        # Ensure we have the expected structure
        if "analyzed_tasks" not in result:
            # If result is a list, wrap it
            if isinstance(result, list):
                result = {"analyzed_tasks": result}
            else:
                # If result is a single task, wrap it in a list
                result = {"analyzed_tasks": [result]}
        
        # Validate and enhance each task
        for task in result.get("analyzed_tasks", []):
            # Ensure rice_breakdown exists
            if "rice_breakdown" not in task:
                task["rice_breakdown"] = {
                    "reach": 5,
                    "impact": 5,
                    "confidence": 5,
                    "effort": 5
                }
            
            # Calculate priority_score if missing
            if "priority_score" not in task:
                task["priority_score"] = format_rice_score(task["rice_breakdown"])
            
            # Ensure other fields
            if "ai_acceleration_factor" not in task:
                task["ai_acceleration_factor"] = 3.0
            if "estimated_hours_traditional" not in task:
                task["estimated_hours_traditional"] = 20
            if "estimated_hours_ai" not in task:
                task["estimated_hours_ai"] = int(task["estimated_hours_traditional"] / task["ai_acceleration_factor"])
            if "cursor_specific_tips" not in task:
                task["cursor_specific_tips"] = "Use Cursor AI to accelerate this task"
        
        return result
        
    except Exception as e:
        return {
            "analyzed_tasks": [],
            "error": f"Error calling Claude API: {str(e)}"
        }

def calculate_performance_score(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score the agent's performance from 1-10000.
    
    Scoring breakdown:
    - Task Coverage (2500 pts): All tasks analyzed successfully
    - Priority Accuracy (2500 pts): Complete RICE data for all tasks
    - AI Leverage (2500 pts): Average acceleration factor (max 5x = 2500)
    - Speed Efficiency (2500 pts): Time saved using AI
    
    Args:
        results: Dictionary with analyzed_tasks from analyze_priorities
        
    Returns:
        Dictionary with total score, max possible, and breakdown
    """
    tasks = results.get("analyzed_tasks", [])
    
    if not tasks:
        return {
            "total_score": 0,
            "max_possible": 10000,
            "breakdown": {
                "task_coverage": 0,
                "priority_accuracy": 0,
                "ai_leverage": 0,
                "speed_efficiency": 0
            },
            "explanation": "No tasks to analyze"
        }
    
    # Task Coverage: 2500 points (all tasks analyzed)
    coverage_score = 2500
    
    # Priority Accuracy: 2500 points
    # Check if each task has complete RICE data
    complete_rice_count = 0
    for task in tasks:
        rice = task.get("rice_breakdown", {})
        if all(key in rice for key in ["reach", "impact", "confidence", "effort"]):
            # Also check that values are within range
            values_valid = all(
                1 <= rice.get(key, 0) <= 10 
                for key in ["reach", "impact", "confidence", "effort"]
            )
            if values_valid:
                complete_rice_count += 1
    
    accuracy_score = (complete_rice_count / len(tasks)) * 2500 if tasks else 0
    
    # AI Leverage: 2500 points
    # Average acceleration factor (capped at 5x for max points)
    total_accel = 0
    accel_count = 0
    for task in tasks:
        accel = task.get("ai_acceleration_factor", 1)
        if accel:
            total_accel += min(float(accel), 5)  # Cap at 5x
            accel_count += 1
    
    if accel_count > 0:
        avg_accel = total_accel / accel_count
        leverage_score = (avg_accel / 5) * 2500
    else:
        leverage_score = 0
    
    # Speed Efficiency: 2500 points
    # Compare traditional hours vs AI hours
    total_traditional = 0
    total_ai = 0
    valid_time_tasks = 0
    
    for task in tasks:
        trad = task.get("estimated_hours_traditional", 0)
        ai = task.get("estimated_hours_ai", 0)
        
        if trad and trad > 0:
            total_traditional += trad
            # If AI hours not provided or invalid, estimate
            if ai and ai > 0:
                total_ai += ai
            else:
                # Estimate based on acceleration factor
                accel = task.get("ai_acceleration_factor", 1)
                total_ai += trad / max(accel, 1)
            valid_time_tasks += 1
    
    if total_traditional > 0 and valid_time_tasks > 0:
        time_saved_ratio = (total_traditional - total_ai) / total_traditional
        # Ensure ratio is between 0 and 1
        time_saved_ratio = max(0, min(1, time_saved_ratio))
        speed_score = time_saved_ratio * 2500
    else:
        speed_score = 0
    
    # Calculate total score
    total = coverage_score + accuracy_score + leverage_score + speed_score
    
    # Ensure total doesn't exceed max
    total = min(10000, total)
    
    # Generate explanation
    explanation = f"Analyzed {len(tasks)} tasks. "
    explanation += f"Complete RICE data: {complete_rice_count}/{len(tasks)}. "
    if accel_count > 0:
        explanation += f"Avg AI acceleration: {avg_accel:.1f}x. "
    if total_traditional > 0:
        time_saved_pct = ((total_traditional - total_ai) / total_traditional * 100)
        explanation += f"Time saved: {time_saved_pct:.0f}%."
    
    return {
        "total_score": round(total),
        "max_possible": 10000,
        "breakdown": {
            "task_coverage": round(coverage_score),
            "priority_accuracy": round(accuracy_score),
            "ai_leverage": round(leverage_score),
            "speed_efficiency": round(speed_score)
        },
        "explanation": explanation
    }

def validate_api_key() -> bool:
    """
    Validate that the API key is working by making a simple test call.
    
    Returns:
        True if API key is valid, False otherwise
    """
    try:
        # Make a minimal test call
        response = client.messages.create(
            model="claude-3-sonnet-20241022",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": "Say 'OK' if you can hear me."
            }]
        )
        return True
    except Exception:
        return False

# For backward compatibility
def get_rice_score(rice_breakdown: Dict[str, int]) -> int:
    """Alias for format_rice_score for backward compatibility"""
    return format_rice_score(rice_breakdown)

if __name__ == "__main__":
    # Test the module when run directly
    print(" Testing AI Priority Agent module...")
    
    # Test format_rice_score
    test_rice = {"reach": 8, "impact": 7, "confidence": 6, "effort": 3}
    score = format_rice_score(test_rice)
    print(f" RICE score test: {score}/10000")
    
    # Test calculate_performance_score with sample data
    sample_results = {
        "analyzed_tasks": [
            {
                "id": "T001",
                "name": "Sample Task",
                "rice_breakdown": {"reach": 8, "impact": 7, "confidence": 6, "effort": 3},
                "ai_acceleration_factor": 4,
                "estimated_hours_traditional": 40,
                "estimated_hours_ai": 10
            }
        ]
    }
    perf_score = calculate_performance_score(sample_results)
    print(f" Performance score test: {perf_score['total_score']}/10000")
    
    # Check API key
    if api_key:
        print(" API key found in environment")
        if validate_api_key():
            print(" API key is valid")
        else:
            print("  API key validation failed - check your key")
    else:
        print(" No API key found - check your .env file")
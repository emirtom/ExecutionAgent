import json
import os
import argparse
from datetime import datetime

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def main():
    parser = argparse.ArgumentParser(description="Analyze Execution Agent logs and optionally insert into PostgreSQL.")
    parser.add_argument("workspace_root", help="Path to the execution_agent_workspace directory")
    args = parser.parse_args()

    workspace_root = args.workspace_root
    summary_path = os.path.join(workspace_root, "launcher_summary.json")
    logs_dir = os.path.join(workspace_root, "_run_logs")
    metadata_dir = os.path.join(workspace_root, "metadata")

    if HAS_DOTENV:
        load_dotenv()
    
    db_url = os.environ.get("DATABASE_URL")

    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            try:
                summary = json.load(f)
            except json.JSONDecodeError:
                pass

    # Fallback: manually crawl _run_logs if summary is empty
    if not summary:
        print("Launcher summary empty/missing. Crawling directories...")
        if os.path.exists(logs_dir):
            for slug in os.listdir(logs_dir):
                project_log_dir = os.path.join(logs_dir, slug)
                if not os.path.isdir(project_log_dir):
                    continue
                
                timestamps = os.listdir(project_log_dir)
                if not timestamps:
                    continue
                
                latest_ts = sorted(timestamps)[-1]
                agent_state_path = os.path.join(project_log_dir, latest_ts, "agent_state.json")
                
                potential_hyphen_slug = slug.replace("_", "-")
                meta_path = os.path.join(metadata_dir, f"meta_{slug}.json")
                if not os.path.exists(meta_path):
                    meta_path = os.path.join(metadata_dir, f"meta_{potential_hyphen_slug}.json")

                project_url = "unknown"
                if os.path.exists(meta_path):
                    with open(meta_path, 'r') as f:
                        try:
                            meta = json.load(f)
                            project_url = meta.get('project_url', 'unknown')
                        except json.JSONDecodeError:
                            pass

                status = "failed"
                if os.path.exists(agent_state_path):
                    with open(agent_state_path, 'r') as f:
                        try:
                            state = json.load(f)
                            if state.get('analysis_succeeded'):
                                status = "success"
                        except json.JSONDecodeError:
                            pass
                
                summary[slug] = {
                    "url": project_url,
                    "status": status
                }

    total_projects = len(summary)
    success_count = 0
    build_success_test_fail_count = 0
    run_records = []

    print(f"{'Project':<20} | {'Status':<10} | {'Build Passed':<12} | {'Smoke Test Passed':<17} | {'GitHub URL'}")
    print("-" * 100)

    for slug, data in summary.items():
        project_url = data.get('url', 'unknown')
        status = data.get('status', 'unknown')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration_ms = int(data.get('duration_seconds', 0) * 1000)
        
        if status == 'success':
            success_count += 1
        
        build_passed = False
        smoke_test_passed = False
        iteration_count = 0
        final_dockerfile = None
        
        if status == 'success':
            build_passed = True
            smoke_test_passed = True
        
        project_log_dir = os.path.join(logs_dir, slug.replace("-", "_"))
        if os.path.exists(project_log_dir):
            timestamps = os.listdir(project_log_dir)
            if timestamps:
                latest_ts = sorted(timestamps)[-1]
                # Precise timestamps if launcher summary is missing
                if not start_time:
                    try:
                        start_time = datetime.strptime(latest_ts, "%Y%m%d_%H%M%S").isoformat()
                    except:
                        pass

                agent_state_path = os.path.join(project_log_dir, latest_ts, "agent_state.json")
                if os.path.exists(agent_state_path):
                    with open(agent_state_path, 'r') as f:
                        try:
                            state = json.load(f)
                            iteration_count = state.get('cycle_count', 0)
                            if state.get('container_id') is not None:
                                build_passed = True
                                if status != 'success':
                                    build_success_test_fail_count += 1
                            
                            # Get final Dockerfile if possible
                            written = state.get('written_files', [])
                            if written:
                                final_dockerfile = written[-1][-1] # Get content of last written file
                        except json.JSONDecodeError:
                            pass

        run_records.append({
            "id": f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "repo_url": project_url,
            "repo_slug": slug,
            "status": status,
            "started_at": start_time,
            "finished_at": end_time,
            "duration_ms": duration_ms,
            "iteration_count": iteration_count,
            "final_dockerfile": final_dockerfile,
            "build_passed": build_passed,
            "smoke_test_passed": smoke_test_passed
        })
        
        print(f"{slug:<20} | {status:<10} | {str(build_passed):<12} | {str(smoke_test_passed):<17} | {project_url}")

    success_rate = (success_count / total_projects) * 100 if total_projects > 0 else 0
    test_fail_rate = (build_success_test_fail_count / total_projects) * 100 if total_projects > 0 else 0

    print("\n" + "="*30)
    print(f"Total Projects: {total_projects}")
    print(f"Success Count: {success_count}")
    print(f"Build Success Count: {success_count + build_success_test_fail_count}")
    print(f"Build Success Test Fail Count: {build_success_test_fail_count}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Build Success Test Fail Rate: {test_fail_rate:.2f}%")
    print("="*30)

    # Prepare batch record
    earliest_start = min((r['started_at'] for r in run_records if r['started_at']), default=None)
    latest_end = max((r['finished_at'] for r in run_records if r['finished_at']), default=None)

    batch_record = {
        "id": f"batch_{datetime.now().strftime('%Y%m%d')}",
        "started_at": earliest_start,
        "finished_at": latest_end,
        "worker_count": 8,
        "repo_count": total_projects,
        "success_count": success_count,
        "build_success_count": success_count + build_success_test_fail_count,
        "failure_count": total_projects - success_count,
        "tag": "execution-agent-eval",
        "ablation": "execution-agent"
    }

    # Database insertion
    if HAS_PSYCOPG2:
        if db_url:
            print(f"\nConnecting to database...")
            try:
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor()
                
                # Insert Batch
                cursor.execute("""
                    INSERT INTO batch_run (id, started_at, finished_at, worker_count, repo_count, success_count, build_success_count, failure_count, tag, ablation)
                    VALUES (%(id)s, %(started_at)s, %(finished_at)s, %(worker_count)s, %(repo_count)s, %(success_count)s, %(build_success_count)s, %(failure_count)s, %(tag)s, %(ablation)s)
                    ON CONFLICT (id) DO UPDATE SET
                        finished_at = EXCLUDED.finished_at,
                        success_count = EXCLUDED.success_count,
                        build_success_count = EXCLUDED.build_success_count,
                        failure_count = EXCLUDED.failure_count;
                """, batch_record)
                
                # Insert Runs
                for run in run_records:
                    run['batch_id'] = batch_record['id']
                    cursor.execute("""
                        INSERT INTO run (id, batch_id, repo_url, repo_slug, status, started_at, finished_at, duration_ms, iteration_count, final_dockerfile, build_passed, smoke_test_passed)
                        VALUES (%(id)s, %(batch_id)s, %(repo_url)s, %(repo_slug)s, %(status)s, %(started_at)s, %(finished_at)s, %(duration_ms)s, %(iteration_count)s, %(final_dockerfile)s, %(build_passed)s, %(smoke_test_passed)s)
                        ON CONFLICT (id) DO NOTHING;
                    """, run)
                
                conn.commit()
                print("Successfully inserted data into PostgreSQL!")
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"Database error: {e}")
        else:
            print("\nDATABASE_URL not found in environment variables. Check your .env file.")
    else:
        print("\npsycopg2 not installed. Use 'pip install psycopg2-binary' to enable DB insertion.")
        print("\nBatch data to insert:")
        print(json.dumps(batch_record, indent=2))

if __name__ == "__main__":
    main()

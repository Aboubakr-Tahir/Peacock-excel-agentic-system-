from config import excel_path, context_path, profiler_notes_path, review_notes_path, repo_path, media_json_path

def run_preprocessing(manager):
    extractor = manager.get_data_extractor_agent()
    extractor.run()
    print("✅ All Data extracted successfully")

    scout = manager.get_scout_agent()
    scout_response = scout.run(f"Run the initial data scout on '{excel_path}' and save the report to '{context_path}'.")
    print(f"✅ Scout Agent finished")

    profiler = manager.get_profiler_agent()
    profiler_response = profiler.run(f"Analyze the data in '{excel_path}' to understand its business context and save your findings to '{profiler_notes_path}'.")
    print(f"✅ Profiler Agent finished")

    analyst = manager.get_analyst_agent()
    analyst_response = analyst.run(f"Read the scout report from 'context.json' and the profiler notes from 'context_notes.txt'. Then, perform a deeper analysis on the file at {excel_path} and update the report at {context_path} with all findings.")
    print("✅ Analyst First Pass Complete")

    print("Reviewing the preprocessing analysis ...")
    reviewer = manager.get_preprocessing_reviewer_agent()
    reviewer_response = reviewer.run(f"Review the JSON report at 'context.json' for logical errors and save your findings to '{review_notes_path}'.")
    print(f"✅ Review Complete")

    print("Running Analyst Agent (Correction Pass) ...")
    if review_notes_path.exists() and review_notes_path.stat().st_size > 0:
        correction_response = analyst.run(f"A review of your previous work has been completed. The notes are in 'review_notes.txt'. Please read the notes and correct the JSON report at 'context.json' accordingly.")
        print("✅ Full Inspection and Correction Workflow Complete")
    else:
        print("❌ No review notes found or review notes were empty. The report is considered final.")

    workspace = manager.get_workspace_agent(context_note_path=profiler_notes_path, context_path=context_path, repo_path=repo_path, media_json_path=media_json_path)
    workspace.run()
    print("✅ The workspace is ready\n")
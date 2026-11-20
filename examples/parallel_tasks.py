"""Run with python examples/parallel_tasks.py after installing the package."""

from multitor import TaskExecutor


def square(value: int) -> int:
    return value * value


if __name__ == "__main__":
    with TaskExecutor(threads=2, processes=2, capacity=8) as executor:
        background = executor.submit(square, 7)  # Returns immediately.
        cpu_job = executor.submit(square, 12, process=True)
        print(background.result(timeout=10))  # Wait only when needed.
        print(cpu_job.result(timeout=30))

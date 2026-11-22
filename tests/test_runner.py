from __future__ import annotations

import copy
import unittest

from runner.constraints import check_constraints
from runner.loader import parse_target
from runner.models import ModelSpec, ParamMapping, WorkflowMap
from runner.plan import plan_shot
from runner.workflow import apply_params, topology_hash
from runner.validate import validate


def sample_workflow() -> dict:
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "model": ["2", 0],
            },
            "_meta": {"title": "SAMPLER"},
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "example.safetensors"},
            "_meta": {"title": "CHECKPOINT"},
        },
    }


class WorkflowTests(unittest.TestCase):
    def test_apply_params_does_not_mutate_source(self) -> None:
        workflow = sample_workflow()
        original = copy.deepcopy(workflow)
        mapping = WorkflowMap(
            params={
                "sampler.seed": ParamMapping(
                    node_title="SAMPLER", input="seed"
                ),
                "model.checkpoint": ParamMapping(
                    node_title="CHECKPOINT", input="ckpt_name"
                ),
            }
        )
        result, applied, warnings, errors = apply_params(
            workflow,
            mapping,
            {"sampler.seed": 42, "model.checkpoint": "other.safetensors"},
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(result["1"]["inputs"]["seed"], 42)
        self.assertEqual(result["2"]["inputs"]["ckpt_name"], "other.safetensors")
        self.assertEqual(workflow, original)
        self.assertEqual(applied["sampler.seed"], 42)

    def test_missing_node_title_is_an_error(self) -> None:
        mapping = WorkflowMap(
            params={
                "sampler.seed": ParamMapping(
                    node_title="MISSING", input="seed"
                )
            }
        )
        _, _, _, errors = apply_params(sample_workflow(), mapping, {"sampler.seed": 42})
        self.assertTrue(errors)
        self.assertIn("MISSING", errors[0])

    def test_topology_hash_ignores_scalar_values(self) -> None:
        first = sample_workflow()
        second = copy.deepcopy(first)
        second["1"]["inputs"]["seed"] = 999
        self.assertEqual(topology_hash(first), topology_hash(second))
        second["1"]["inputs"]["model"] = ["1", 0]
        self.assertNotEqual(topology_hash(first), topology_hash(second))


class ConstraintTests(unittest.TestCase):
    def test_frames_expression(self) -> None:
        model = ModelSpec(kind="video", constraints={"frames": "4n+1"})
        errors, _ = check_constraints(model, {"video.frames": 49})
        self.assertEqual(errors, [])
        errors, _ = check_constraints(model, {"video.frames": 50})
        self.assertTrue(errors)

    def test_resolution_multiple(self) -> None:
        model = ModelSpec(
            kind="image",
            constraints={"width_multiple": 16, "height_multiple": 16},
        )
        errors, _ = check_constraints(model, {"image.width": 832, "image.height": 480})
        self.assertEqual(errors, [])
        errors, _ = check_constraints(model, {"image.width": 830, "image.height": 480})
        self.assertTrue(errors)


class TargetTests(unittest.TestCase):
    def test_parse_target(self) -> None:
        self.assertEqual(parse_target("demo_01"), ("demo_01", None))
        self.assertEqual(parse_target("demo_01/s010"), ("demo_01", "s010"))
        self.assertEqual(
            parse_target("projects/demo_01/shots/s010"),
            ("demo_01", "s010"),
        )


class DemoTests(unittest.TestCase):
    def test_demo_plan_resolves(self) -> None:
        plan = plan_shot("demo_01", "s010")
        self.assertFalse(plan.errors, plan.errors)
        keyframe = next(stage for stage in plan.stages if stage.id == "keyframe")
        self.assertEqual(keyframe.applied["sampler.seed"], 123456)
        self.assertEqual(
            keyframe.applied["output.prefix"],
            "demo_01/s010/keyframe/v001",
        )

    def test_demo_validates(self) -> None:
        report = validate(no_git=True)
        self.assertTrue(report.ok, report.errors)


if __name__ == "__main__":
    unittest.main()

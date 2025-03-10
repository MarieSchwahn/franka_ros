#!/usr/bin/env python

import sys
import rospy as ros
import time

from actionlib import SimpleActionClient
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import FollowJointTrajectoryAction, \
                             FollowJointTrajectoryGoal, FollowJointTrajectoryResult, GripperCommandActionGoal


class Bring_out_platform:
    """Send commands for platform to move to base station of platform, grip it and bring it to WS center.
    """

    def __init__(self):
        ros.init_node('bring_out_platform')

        self.action = ros.resolve_name('~follow_joint_trajectory')
        self.client = SimpleActionClient(self.action, FollowJointTrajectoryAction)
        ros.loginfo("bring_out_platform: Waiting for '" + self.action + "' action to come up")
        self.client.wait_for_server()

        self.param_0 = ros.resolve_name('~start_joint_pose')
        self.param_1 = ros.resolve_name('~intermediate_joint_pose_0')
        self.param_2 = ros.resolve_name('~approach_platform_joint_pose')
        self.param_3 = ros.resolve_name('~grab_platform_joint_pose')
        self.param_4 = ros.resolve_name('~lift_platform_joint_pose')
        self.param_5 = ros.resolve_name('~intermediate_joint_pose_1')
        self.param_6 = ros.resolve_name('~ws_center_joint_pose')
        self.pose_0 = ros.get_param(self.param_0, None)
        self.pose_1 = ros.get_param(self.param_1, None)
        self.pose_2 = ros.get_param(self.param_2, None)
        self.pose_3 = ros.get_param(self.param_3, None)
        self.pose_4 = ros.get_param(self.param_4, None)
        self.pose_5 = ros.get_param(self.param_5, None)
        self.pose_6 = ros.get_param(self.param_6, None)

        self.poses = [self.pose_0, self.pose_1, self.pose_2, self.pose_3, self.pose_4, self.pose_5, self.pose_6]

        self.gripper_close_cmd = GripperCommandActionGoal()
        self.gripper_close_cmd.goal.command.position = 0.02
        self.gripper_close_cmd.goal.command.max_effort = 1.0

        self.gripper_open_cmd = GripperCommandActionGoal()
        self.gripper_open_cmd.goal.command.position = 0.033
        self.gripper_open_cmd.goal.command.max_effort = 1.0
        self.pub_gripper_cmd = ros.Publisher("/franka_gripper/gripper_action/goal", GripperCommandActionGoal, queue_size=10)

        self.main()

        ros.spin()

    def main(self):
        time.sleep(10)
        self.pub_gripper_cmd.publish(self.gripper_open_cmd)

        for i, pose in enumerate(self.poses):
            # After aligning gripper with platform handle: grip platform
            if i == 4:
                time.sleep(1)
                self.pub_gripper_cmd.publish(self.gripper_close_cmd)
                time.sleep(1.5)
            if pose is None:
                ros.logerr('bring platform out: Could not find required parameter ')
                sys.exit(1)
            topic = ros.resolve_name('~joint_states')
            ros.loginfo("bring platform out: Waiting for message on topic '" + topic + "'")
            joint_state = ros.wait_for_message(topic, JointState)
            initial_pose = dict(zip(joint_state.name, joint_state.position))

            max_movement = max(abs(pose[joint] - initial_pose[joint]) for joint in pose)

            point = JointTrajectoryPoint()
            point.time_from_start = ros.Duration.from_sec(
                # Use either the time to move the furthest joint with 'max_dq' or 500ms,
                # whatever is greater
                max(max_movement / ros.get_param('~max_dq', 0.1), 0.1)
            )
            goal = FollowJointTrajectoryGoal()

            goal.trajectory.joint_names, point.positions = [list(x) for x in zip(*pose.items())]
            point.velocities = [0] * len(pose)

            goal.trajectory.points.append(point)
            goal.goal_time_tolerance = ros.Duration.from_sec(0.5)

            ros.loginfo('Sending trajectory Goal to move into next config')
            self.client.send_goal_and_wait(goal)

            result = self.client.get_result()
            if result.error_code != FollowJointTrajectoryResult.SUCCESSFUL:
                ros.logerr('bring_out_platform: Movement was not successful: ' + {
                    FollowJointTrajectoryResult.INVALID_GOAL:
                    """
                    The joint pose you want to move to is invalid (e.g. unreachable, singularity...).
                    Is the 'joint_pose' reachable?
                    """,

                    FollowJointTrajectoryResult.INVALID_JOINTS:
                    """
                    The joint pose you specified is for different joints than the joint trajectory controller
                    is claiming. Does you 'joint_pose' include all 7 joints of the robot?
                    """,

                    FollowJointTrajectoryResult.PATH_TOLERANCE_VIOLATED:
                    """
                    During the motion the robot deviated from the planned path too much. Is something blocking
                    the robot?
                    """,

                    FollowJointTrajectoryResult.GOAL_TOLERANCE_VIOLATED:
                    """
                    After the motion the robot deviated from the desired goal pose too much. Probably the robot
                    didn't reach the joint_pose properly
                    """,
                }[result.error_code])

            else:
                ros.loginfo('bring_out_platform: Successfully moved platform to WS center')




bring_out_platform = Bring_out_platform()
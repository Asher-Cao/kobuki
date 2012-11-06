import roslib; roslib.load_manifest('kobuki_testsuite')
import rospy
import threading

from tf.transformations import euler_from_quaternion
from math import degrees, radians

import sys
import random

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from kobuki_comms.msg import BumperEvent, CliffEvent

# Local imports
import utils

'''
  Implements a safe wandering random motion using bump and cliff sensors. 

      API:
        init(speed,distance) : (re)initialise parameters 
        stop()  - stop.
        execute() - pass this to a thread to run
        shutdown() - cleanup
      
      @param topic names
      @type strings

'''
class SafeWandering(object):
    '''
      Initialise everything, then starts with start()

      API:
        start() - start to wander. 
        stop()  - stop wandering.
        set_vels(lin_xvel,stepback_xvel,ang_zvel)
      
      @param topic names
      @type strings
    '''
    def __init__(self, cmd_vel_topic, odom_topic, bumper_topic, cliff_topic ):
        threading.Thread.__init__(self)

        bumper_subscriber = rospy.Subscriber(bumper_topic, BumperEvent, self.bumper_event_callback)
        cliff_subscriber = rospy.Subscriber(cliff_topic, CliffEvent, self.cliff_event_callback)
        odom_subscriber = rospy.Subscriber(odom_topic, Odometry, self.odometry_callback)
        self.cmd_vel_publisher = rospy.Publisher(cmd_vel_topic, Twist)
        self.rate = rospy.Rate(50)

        self.ok = True
        self.theta = 0.0
        self.theta_goal = 0.0
        self._stop = False
        self._running = False

        self._lin_xvel = 0.18
        self._stepback_xvel = -0.1
        self._ang_zvel = 1.8
        
    def shutdown(self):
        self.stop()
        while self._running():
            rospy.sleep(0.05)
        self.cmd_vel_publisher.unregister()
        self.odom_subscriber.unregister()
        self.bumper_subscriber.unregister()
        self.cliff_subscriber.unregister()

    def command(self, twist):
        self.cmd_vel_publisher.publish(twist)
        self.rate.sleep()
        if rospy.is_shutdown():
            sys.exit()

    def go(self):
        twist = Twist()
        twist.linear.x = self._lin_xvel
        while self.ok:
            self.command(twist)

    def stepback(self):
        twist = Twist()
        twist.linear.x = self._stepback_xvel
        for i in range(0,35): 
            self.command(twist)
 
    def turn(self):
        twist = Twist()
        twist.angular.z = self._ang_zvel * utils.sign(utils.wrap_to_pi(self.theta_goal - self.theta))
        while not self.reached():
            self.command(twist)
        self.ok = True

    def reached(self):
        if abs(utils.wrap_to_pi(self.theta_goal - self.theta)) < radians(5.0):
            return True
        else:
            return False

    def stop(self):
        self._stop = True

    def execute(self):
        if self._running:
            rospy.logerr("Kobuki TestSuite: already executing wandering, ignoring the request")
            return
        self._stop = False
        self._running = True
        while not self._stop and not rospy.is_shutdown():
            self.go()
            self.stepback()
            self.turn()
        self._running = False

    def set_vels(self,lin_xvel,stepback_xvel,ang_zvel):
        self._lin_xvel = lin_xvel
        self._stepback_xvel = stepback_xvel
        self._ang_zvel = ang_zvel

    ##########################################################################
    # Callbacks
    ##########################################################################

    def odometry_callback(self, data):
        quat = data.pose.pose.orientation
        q = [quat.x, quat.y, quat.z, quat.w]
        roll, pitch, yaw = euler_from_quaternion(q)
        self.theta = yaw

      
    def bumper_event_callback(self, data):
        if data.state == BumperEvent.PRESSED:
            self.ok = False
            if   data.bumper == BumperEvent.LEFT:
                self.theta_goal = self.theta - 3.141592*random.uniform(0.2, 1.0)
            elif data.bumper == BumperEvent.RIGHT:
                self.theta_goal = self.theta + 3.141592*random.uniform(0.2, 1.0)
            else:
                self.theta_goal = utils.wrap_to_pi(self.theta + 3.141592*random.uniform(-1.0, 1.0))

    def cliff_event_callback(self, data):
        if data.state == CliffEvent.CLIFF:
            self.ok = False
            if   data.sensor == CliffEvent.LEFT:
                self.theta_goal = self.theta - 3.141592*random.uniform(0.2, 1.0)
            elif data.sensor == CliffEvent.RIGHT:
                self.theta_goal = self.theta + 3.141592*random.uniform(0.2, 1.0)
            else:
                self.theta_goal = utils.wrap_to_pi(self.theta + 3.141592*random.uniform(-1.0, 1.0))
 
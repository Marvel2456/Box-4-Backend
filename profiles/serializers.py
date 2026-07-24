from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import BuyerProfile, AgentProfile, AdminProfile

User = get_user_model()

class UserProfileDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role')
        read_only_fields = ('id', 'email', 'role')


class BaseProfileSerializer(serializers.ModelSerializer):
    user = UserProfileDetailSerializer(read_only=True)
    full_name = serializers.CharField(write_only=True, required=False)

    def update_user_names(self, instance, validated_data):
        full_name = validated_data.pop('full_name', None)
        
        user = instance.user
        if full_name is not None:
            user.full_name = full_name
            user.save()
            
        return validated_data


class BuyerProfileSerializer(BaseProfileSerializer):
    class Meta:
        model = BuyerProfile
        fields = (
            'id', 'user', 'full_name', 'phone_number', 'profile_picture',
            'latitude', 'longitude', 'city', 'state', 'country', 'bio'
        )
        read_only_fields = ('id',)

    def update(self, instance, validated_data):
        validated_data = self.update_user_names(instance, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AgentProfileSerializer(BaseProfileSerializer):
    class Meta:
        model = AgentProfile
        fields = (
            'id', 'user', 'full_name', 'phone_number', 'profile_picture',
            'latitude', 'longitude', 'city', 'state', 'country', 'bio',
            'agency_name', 'license_number', 'rating'
        )
        read_only_fields = ('id', 'rating')

    def update(self, instance, validated_data):
        validated_data = self.update_user_names(instance, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AdminProfileSerializer(BaseProfileSerializer):
    class Meta:
        model = AdminProfile
        fields = (
            'id', 'user', 'full_name', 'phone_number', 'profile_picture', 'bio'
        )
        read_only_fields = ('id',)

    def update(self, instance, validated_data):
        validated_data = self.update_user_names(instance, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class BuyerProfileOnboardingSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = BuyerProfile
        fields = ('phone_number', 'latitude', 'longitude', 'city', 'state', 'country', 'bio')


class AgentProfileOnboardingSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = AgentProfile
        fields = ('phone_number', 'latitude', 'longitude', 'city', 'state', 'country', 'bio', 'agency_name', 'license_number')


class AdminProfileOnboardingSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = AdminProfile
        fields = ('phone_number', 'bio')
